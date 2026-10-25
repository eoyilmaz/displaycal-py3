"""Tests for the DisplayCAL.multiprocess module."""

import io
import os
import signal
import sys
import threading

import pytest

from DisplayCAL import multiprocess
from DisplayCAL.multiprocess import (
    MP_CONTEXT,
    NonDaemonicPool,
    WorkerProcessError,
    describe_exitcode,
    pool_slice,
)


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
