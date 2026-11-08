"""Tests for the DisplayCAL.multiprocess module."""

from __future__ import annotations

import io
import os
import pickle
import signal
import sys
import threading
import time
from typing import TYPE_CHECKING

import pytest

from DisplayCAL import multiprocess
from DisplayCAL.multiprocess import (
    MP_CONTEXT,
    NonDaemonicPool,
    WorkerProcessError,
    describe_exitcode,
    pool_slice,
)

if TYPE_CHECKING:
    from multiprocessing.queues import SimpleQueue
    from multiprocessing.synchronize import Event


def _square(chunk, thread_abort_event, progress_queue, offset=0):
    """Worker function returning the squares of the chunk items."""
    progress_queue.put(100)
    return [value * value + offset for value in chunk]


def _crash(chunk, thread_abort_event, progress_queue):
    """Worker function that kills its own process like a native crash would."""
    if chunk and chunk[0] == 0:
        os.kill(os.getpid(), signal.SIGTERM)
    progress_queue.put(100)
    return chunk


def _hold_worker(ready: Event) -> None:
    """Keep the worker outside inqueue.get() during termination."""
    ready.set()
    threading.Event().wait(30)


def test_mp_context_is_spawn():
    """Worker processes are never forked from the (multithreaded) GUI process."""
    assert MP_CONTEXT.get_start_method() == "spawn"


def test_non_daemonic_pool_uses_spawn_context():
    """The pool and its (class-swapped) worker processes use "spawn"."""
    pool = NonDaemonicPool(1)
    try:
        assert pool._ctx is MP_CONTEXT
        assert len(pool._all_workers) == 1
        proc = pool._all_workers[0]
        assert isinstance(proc, MP_CONTEXT.Process)
        assert proc.daemon is False
        # mp.Process._Popen would use the platform default (fork on Linux)
        assert proc._Popen is MP_CONTEXT.Process._Popen
    finally:
        pool.terminate()
        pool.join()


@pytest.mark.parametrize(
    ("queue_name", "shutdown"),
    [
        ("_change_notifier", "close"),
        ("_change_notifier", "terminate"),
        ("_outqueue", "terminate"),
    ],
    ids=["notifier-close", "notifier-terminate", "results-terminate"],
)
@pytest.mark.parametrize(
    "native_pipe",
    [
        False,
        pytest.param(
            True,
            marks=pytest.mark.skipif(
                sys.platform != "win32", reason="Windows named pipe"
            ),
        ),
    ],
    ids=["emulated-pipe", "native-pipe"],
)
def test_pool_shutdown_serializes_parent_queue_writes(  # noqa: C901
    monkeypatch: pytest.MonkeyPatch,
    queue_name: str,
    shutdown: str,
    native_pipe: bool,
) -> None:
    """Pool shutdown cannot overlap another parent thread's Windows pipe write."""
    sending = threading.Lock()
    result_writing = threading.Event()
    result_written = threading.Event()
    reader_waiting = threading.Event()
    release_result = threading.Event()
    allow_shutdown = threading.Event()
    shutdown_started = threading.Event()
    shutdown_finished = threading.Event()
    worker_ready = MP_CONTEXT.Event()
    errors = []
    original_setup = multiprocess.mp.pool.Pool._setup_queues
    original_init = multiprocess.mp.pool.Pool.__init__
    original_help = NonDaemonicPool._help_stuff_finish

    def windows_setup(self: NonDaemonicPool) -> None:
        original_setup(self)
        if queue_name == "_outqueue":
            # Apply Windows semantics before our override and worker spawning.
            self._outqueue._wlock = None
            if native_pipe:
                original_recv = self._quick_get

                def recv() -> object:
                    reader_waiting.set()
                    if not release_result.wait(5):
                        raise TimeoutError("test did not release result reader")
                    return original_recv()

                self._quick_get = recv

    def help_finish(
        inqueue: SimpleQueue, task_handler: threading.Thread, size: int
    ) -> None:
        original_help(inqueue, task_handler, size)
        # The busy worker leaves inqueue._rlock free. Hold the terminating
        # caller here until the task handler's result sentinel is in flight.
        if not allow_shutdown.wait(5):
            raise TimeoutError("test did not release pool termination")

    def windows_pool_init(self: NonDaemonicPool, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        # Windows SimpleQueue has no write lock. Emulate that on every OS,
        # before NonDaemonicPool installs its parent-thread synchronization.
        self._change_notifier._wlock = None

    monkeypatch.setattr(multiprocess.mp.pool.Pool, "__init__", windows_pool_init)
    monkeypatch.setattr(multiprocess.mp.pool.Pool, "_setup_queues", windows_setup)
    if queue_name == "_outqueue":
        monkeypatch.setattr(
            NonDaemonicPool, "_help_stuff_finish", staticmethod(help_finish)
        )
        pool = NonDaemonicPool(1, initializer=_hold_worker, initargs=(worker_ready,))
        writing_thread = pool._task_handler
    else:
        pool = NonDaemonicPool(1)
        writing_thread = pool._result_handler
    notifier = getattr(pool, queue_name)
    original_send = notifier._writer.send_bytes
    original_put = notifier.put
    original_get = notifier.get

    def send_bytes(data: bytes | memoryview) -> None:
        if native_pipe:
            try:
                if threading.current_thread() is writing_thread:
                    # Exceed the Windows pipe buffer while its reader is
                    # paused, leaving a real overlapped WriteFile pending.
                    data = pickle.dumps(None) + bytes(1024 * 1024)
                return original_send(data)
            finally:
                if threading.current_thread() is writing_thread:
                    result_written.set()
        # PipeConnection on Windows rejects a second send on the same object
        # while the first overlapped WriteFile is still pending.
        if not sending.acquire(blocking=False):
            raise ValueError("concurrent send_bytes() calls are not supported")
        try:
            if threading.current_thread() is writing_thread:
                result_writing.set()
                if not release_result.wait(5):
                    raise TimeoutError("test did not release result notification")
            return original_send(data)
        finally:
            sending.release()
            if threading.current_thread() is writing_thread:
                result_written.set()

    def put(value: object) -> None:
        if threading.current_thread() is closer:
            shutdown_started.set()
        return original_put(value)

    def get() -> object:
        reader_waiting.set()
        if not release_result.wait(5):
            raise TimeoutError("test did not release pipe reader")
        return original_get()

    def finish_pool() -> None:
        try:
            getattr(pool, shutdown)()
        except Exception as error:
            errors.append((type(error), str(error)))
        finally:
            shutdown_finished.set()

    closer = threading.Thread(target=finish_pool)
    monkeypatch.setattr(notifier._writer, "send_bytes", send_bytes)
    monkeypatch.setattr(notifier, "put", put)
    if native_pipe and queue_name == "_change_notifier":
        monkeypatch.setattr(notifier, "get", get)
    try:
        if queue_name == "_outqueue":
            assert worker_ready.wait(5)
            closer.start()
        else:
            result = pool.apply_async(abs, (-1,))
        if native_pipe:
            assert reader_waiting.wait(5)
            deadline = time.monotonic() + 5
            while notifier._writer._send_ov is None and time.monotonic() < deadline:
                time.sleep(0.01)
            assert notifier._writer._send_ov is not None
        else:
            assert result_writing.wait(5)
        if queue_name == "_change_notifier":
            # AsyncResult is ready before the last cache notification finishes.
            assert result.get(5) == 1
            closer.start()
        else:
            allow_shutdown.set()
        assert shutdown_started.wait(5)
        blocked = not shutdown_finished.wait(0.1)
    finally:
        release_result.set()
        allow_shutdown.set()
        result_written.wait(5)
        if closer.ident is not None:
            closer.join(5)
        pool.terminate()
        # A deliberately failing regression consumes Pool's Finalize callback
        # before it can kill the busy worker. Reap only this test's workers.
        for process in pool._pool:
            if process.is_alive():
                process.terminate()
        pool.join()
    assert not closer.is_alive()
    assert errors == []
    assert blocked


def test_result_queue_parent_lock_allows_worker_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spawning and replacing workers never pickles the parent's thread lock."""
    original_setup = multiprocess.mp.pool.Pool._setup_queues

    def windows_setup(self: NonDaemonicPool) -> None:
        original_setup(self)
        self._outqueue._wlock = None

    monkeypatch.setattr(multiprocess.mp.pool.Pool, "_setup_queues", windows_setup)
    pool = NonDaemonicPool(1, maxtasksperchild=1)
    try:
        assert pool._outqueue._wlock is None
        assert pool.apply_async(abs, (-1,)).get(5) == 1
        assert pool.apply_async(abs, (-2,)).get(5) == 2
        assert len(pool._all_workers) >= 2
    finally:
        pool.terminate()
        pool.join()


def test_pool_slice_single_worker():
    """Running in-process with a single worker returns the results."""
    assert pool_slice(_square, list(range(5)), (1,), num_workers=1) == [
        [1, 2, 5, 10, 17]
    ]


def test_pool_slice_multiple_workers():
    """Results of multiple spawned workers are returned in input order."""
    result = pool_slice(_square, list(range(6)), num_workers=2)
    assert [value for chunk in result for value in chunk] == [
        0,
        1,
        4,
        9,
        16,
        25,
    ]


def test_pool_slice_crashed_worker_raises_instead_of_hanging():
    """A worker dying without a result raises instead of waiting forever."""
    logfile = io.StringIO()
    threads_before = set(threading.enumerate())
    with pytest.raises(WorkerProcessError) as cm:
        pool_slice(_crash, list(range(4)), num_workers=2, logfile=logfile)
    assert "died unexpectedly" in str(cm.value)
    # The progress logger thread must not keep the application alive
    for thread in set(threading.enumerate()) - threads_before:
        thread.join(5)
        assert not thread.is_alive()


def test_crashed_worker_restores_abort_event():
    """The original abort event is restored after a worker crash."""

    class ThreadAbort:
        event = threading.Event()

    thread_abort = ThreadAbort()
    original_event = thread_abort.event
    with pytest.raises(WorkerProcessError):
        pool_slice(_crash, list(range(4)), num_workers=2, thread_abort=thread_abort)
    assert thread_abort.event is original_event


@pytest.mark.skipif(sys.platform == "win32", reason="no POSIX signals")
def test_describe_exitcode_signal():
    """Negative exit codes are described by their signal name."""
    assert describe_exitcode(-signal.SIGABRT) == "killed by SIGABRT"


def test_describe_exitcode_unknown_signal():
    """Unknown signal numbers are still described."""
    assert describe_exitcode(-999) == "killed by signal 999"


def test_describe_exitcode_positive():
    """Positive exit codes are described as such."""
    assert describe_exitcode(3) == "exit code 3"


def test_fake_pool_has_no_crashed_workers():
    """The in-process pool never reports crashed workers."""
    assert multiprocess.FakePool().crashed_workers() == []
