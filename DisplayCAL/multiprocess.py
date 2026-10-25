"""Utilities for parallel processing with multiprocessing.

It includes functions and classes to manage worker pools, handle task
distribution, and process data slices efficiently.
"""

from __future__ import annotations

import contextlib
import errno
import logging
import math
import multiprocessing as mp
import multiprocessing.pool
import sys
import threading
from queue import Empty
from typing import TYPE_CHECKING, Any, Callable, TextIO

if TYPE_CHECKING:
    from collections.abc import Iterable


# BUG #715 : Limiting the total workers/CPUs to 32
MAX_CPUS = 32

# BUG #979 : Always spawn worker processes instead of forking them. Forking the
# multithreaded GUI process (wx/Qt, ctypes callbacks, worker threads) on Linux
# can leave the children in an inconsistent state, e.g. garbage collecting an
# inherited ctypes callback aborts in libffi's ffi_closure_free(). Windows and
# macOS already use "spawn" by default.
MP_CONTEXT = mp.get_context("spawn")

# How often (in seconds) to check for crashed worker processes while waiting
# for results.
WORKER_POLL_INTERVAL = 0.5


class WorkerProcessError(RuntimeError):
    """Raised when a worker process died before returning its result."""


def cpu_count(limit_by_total_vmem: bool = True) -> int:
    """Return the number of CPUs in the system.

    If psutil is installed, the number of reported CPUs is limited according to
    total RAM by assuming 1 GB for each CPU + 1 GB for the system, unless
    limit_by_total_vmem is False, to allow a reasonable amount of memory for
    each CPU.

    Return fallback value of 1 if CPU count cannot be determined.

    Args:
        limit_by_total_vmem (bool, optional): If True, limit the reported CPU
            count according to total RAM. Defaults to True.

    Returns:
        int: The number of CPUs in the system, limited by total RAM if
            specified.
    """
    max_cpus = min(sys.maxsize, MAX_CPUS)
    if limit_by_total_vmem:
        try:
            import psutil
        except (ImportError, RuntimeError):
            pass
        else:
            # Limit reported CPUs according to total RAM.
            # We use total instead of available because we assume the system is
            # smart enough to swap memory used by inactive processes to disk to
            # free up more physical RAM for active processes.
            with contextlib.suppress(Exception):
                max_cpus = min(
                    int(psutil.virtual_memory().total / (1024**3) - 1), MAX_CPUS
                )
    try:
        return max(min(mp.cpu_count(), max_cpus), 1)
    except Exception:
        return 1


def pool_slice(
    func: Callable,
    data_in: Iterable,
    args: None | tuple = None,
    kwds: None | dict = None,
    num_workers: None | int = None,
    thread_abort: None | threading.Thread = None,
    logfile: None | TextIO = None,
    num_batches: int = 1,
    progress: float = 0,
) -> list:
    """Process data in slices using a pool of workers and return the results.

    The individual worker results are returned in the same order as the
    original input data, irrespective of the order in which the workers
    finished (FIFO).

    Progress percentage is written to optional logfile using a background
    thread that monitors a queue.

    Note that 'func' is supposed to periodically check thread_abort.event which
    is passed as the first argument to 'func', and put its progress percentage
    into the queue which is passed as the second argument to 'func'.

    Args:
        func (Callable): The function to be applied to each slice of data.
        data_in (Iterable): The input data to be processed.
        args (None | tuple, optional): Additional positional arguments to pass
            to 'func'. Defaults to None.
        kwds (None | dict, optional): Additional keyword arguments to pass to
            'func'. Defaults to None.
        num_workers (None | int, optional): The number of worker processes to
            use. If None, it will be set to the number of CPUs in the system.
            Defaults to None.
        thread_abort (None | threading.Thread, optional): A thread with an
            'event' attribute (threading.Event) that can be used to signal
            abortion of processing. Defaults to None.
        logfile (None | TextIO, optional): A file-like object to write progress
            percentage to. If None, progress will not be logged. Defaults to
            None.
        num_batches (int, optional): The number of batches to split the work
            into. This can be used to limit memory usage when processing a
            large amount of data. Defaults to 1.
        progress (float, optional): Initial progress percentage. Defaults to
            0.

    Returns:
        list: A list of results from processing each slice of data.
    """
    if args is None:
        args = ()

    if kwds is None:
        kwds = {}

    num_workers, num_batches, chunk_size = determine_worker_count(
        data_in, num_workers, num_batches
    )
    pool_class, manager, event, thread_abort_event, progress_queue = (
        initialize_pool_manager(num_workers, thread_abort)
    )
    # don't remove "_thread" to keep the thread alive to log the progress.
    _thread = start_progress_logging(
        num_workers,
        num_batches,
        progress,
        progress_queue,
        logfile,
    )
    pool, results = execute_worker_pool(
        func,
        data_in,
        args,
        kwds,
        num_workers,
        num_batches,
        chunk_size,
        pool_class,
        thread_abort_event,
        progress_queue,
    )
    return get_results(results, pool, manager, event, thread_abort)


def determine_worker_count(
    data_in: Iterable,
    num_workers: None | int,
    num_batches: int,
) -> tuple[int, int, float]:
    """Determine the number of workers, batches, and chunk size.

    Args:
        data_in (Iterable): The input data to be processed.
        num_workers (None | int): The number of worker processes to use.
            If None, it will be set to the number of CPUs in the system.
        num_batches (int): The number of batches to split the work into.

    Returns:
        tuple[int, int, float]: A tuple containing:
            - The number of worker processes to use.
            - The number of batches to split the work into.
            - The size of each chunk to process.
    """
    from DisplayCAL.config import getcfg

    num_workers = cpu_count() if num_workers is None else min(num_workers, MAX_CPUS)
    num_workers = max(min(int(num_workers), len(data_in)), 1)
    max_workers = getcfg("multiprocessing.max_cpus")
    num_workers = min(num_workers, max_workers) if max_workers else num_workers

    # Splitting the workload into batches only makes sense if there are
    # multiple workers
    num_batches = 1 if (num_workers == 1 or not num_batches) else num_workers
    chunk_size = float(len(data_in)) / (num_workers * num_batches)
    if chunk_size < 1:
        num_batches = 1
        chunk_size = float(len(data_in)) / num_workers
    return num_workers, num_batches, chunk_size


def initialize_pool_manager(
    num_workers: int,
    thread_abort: None | threading.Thread,
) -> tuple[
    type,
    None | mp.Manager,
    None | threading.Event,
    None | threading.Event,
    mp.Queue,
]:
    """Initialize the worker pool and manager for inter-process communication.

    Args:
        num_workers (int): The number of worker processes to use.
        thread_abort (None | threading.Thread): A thread with an 'event'
            attribute (threading.Event) that can be used to signal abortion
            of processing. Defaults to None.

    Returns:
        tuple[
            type,
            None | multiprocessing.Manager,
            None | threading.Event,
            None | threading.Event,
            multiprocessing.Queue
        ]: A tuple containing:
            - The class to use for the worker pool.
            - The manager for inter-process communication, or None if not used.
            - The original event from thread_abort, or None if not used.
            - The event to signal thread abort, or None if not used.
            - The queue to send progress updates.
    """
    # Do it all in in the main thread of the current instance, by default
    pool_class = FakePool
    manager = None
    event = None
    queue_class = FakeQueue
    if num_workers > 1:
        pool_class = NonDaemonicPool
        manager = MP_CONTEXT.Manager()
        if thread_abort is not None and not isinstance(
            thread_abort.event, mp.managers.EventProxy
        ):
            # Replace the event with a managed instance that is compatible
            # with pool
            event = thread_abort.event
            thread_abort.event = manager.Event()
            if event.is_set():
                thread_abort.event.set()
        else:
            event = None
        queue_class = manager.Queue

    thread_abort_event = thread_abort.event if thread_abort is not None else None
    progress_queue = queue_class()

    return pool_class, manager, event, thread_abort_event, progress_queue


def start_progress_logging(
    num_workers: int,
    num_batches: int,
    progress: float,
    progress_queue: mp.Queue,
    logfile: None | TextIO,
) -> None | threading.Thread:
    """Start a background thread to log progress percentage to logfile.

    Args:
        num_workers (int): Number of worker processes.
        num_batches (int): The number of batches to split the work into.
        progress (float): Initial progress percentage.
        progress_queue (mp.Queue): Queue to send progress updates.
        logfile (None | TextIO): A file-like object to write progress
            percentage to. If None, progress will not be logged.

    Returns:
        None | threading.Thread: The thread that logs progress, or None if
            logfile is None.
    """
    if not logfile:
        return None

    def progress_logger(num_workers: int, progress: float = 0.0) -> None:
        """Log progress percentage to logfile.

        Args:
            num_workers (int): Number of worker processes.
            progress (float, optional): Initial progress percentage.
                Defaults to 0.0.
        """
        eof_count = 0
        prevperc = -1
        while progress < 100 * num_workers:
            try:
                inc = progress_queue.get(True, 0.1)
                if isinstance(inc, Exception):
                    raise inc
                progress += inc
            except Empty:
                continue
            except OSError:
                break
            except EOFError:
                eof_count += 1
                if eof_count == num_workers:
                    break
            perc = round(progress / num_workers)
            if perc > prevperc:
                logfile.write(f"\r{perc}%")
                prevperc = perc

    thread = threading.Thread(
        target=progress_logger,
        args=(num_workers * num_batches, progress * num_workers * num_batches),
        name="ProcessProgressLogger",
        group=None,
    )
    thread.start()
    return thread


def execute_worker_pool(
    func: Callable,
    data_in: Iterable,
    args: tuple,
    kwds: dict,
    num_workers: int,
    num_batches: int,
    chunk_size: float,
    poll_class: type,
    thread_abort_event: threading.Event,
    progress_queue: mp.Queue,
) -> tuple[NonDaemonicPool | FakePool, list]:
    """Execute worker pool to process data slices.

    Args:
        func (Callable): The function to be applied to each slice of data.
        data_in (Iterable): The input data to be processed.
        args (tuple): Additional positional arguments to pass to 'func'.
        kwds (dict): Additional keyword arguments to pass to 'func'.
        num_workers (int): The number of worker processes to use.
        num_batches (int): The number of batches to split the work into.
        chunk_size (float): The size of each chunk to process.
        poll_class (type): The class to use for the worker pool.
        thread_abort_event (threading.Event): Event to signal thread abort.
        progress_queue (mp.Queue): Queue to send progress updates.

    Returns:
        tuple[NonDaemonicPool | FakePool, list]: The worker pool and a list of
            results from processing each slice of data.
    """
    pool = poll_class(num_workers)
    results = []
    start = 0
    for batch in range(num_batches):
        for i in range(batch * num_workers, (batch + 1) * num_workers):
            end = math.ceil(chunk_size * (i + 1))
            results.append(
                pool.apply_async(
                    WorkerFunc(func, batch == num_batches - 1),
                    (data_in[start:end], thread_abort_event, progress_queue, *args),
                    kwds,
                )
            )
            start = end
    return pool, results


def get_results(
    results: list,
    pool: NonDaemonicPool | FakePool,
    manager: None | multiprocessing.Manager,
    event: None | threading.Event,
    thread_abort: None | threading.Thread,
) -> list:
    """Get results from worker pool and clean up resources.

    Args:
        results (list): List of results from worker pool.
        pool (NonDaemonicPool | FakePool): The worker pool.
        manager (None | multiprocessing.Manager): The manager used for
            inter-process communication.
        event (None | threading.Event): The original event from thread_abort.
        thread_abort (None | threading.Thread): The thread with the event
            attribute.

    Raises:
        Exception: If any of the worker processes raised an exception.

    Returns:
        list: A list of results from the worker processes.
    """
    # Get results
    exception = None
    data_out = []
    try:
        for result in results:
            result = wait_for_result(result, pool)
            if isinstance(result, Exception):
                exception = result
                continue
            data_out.append(result)
    except WorkerProcessError:
        pool.terminate()
        pool.join()
        shutdown_manager(manager, event, thread_abort)
        raise

    pool.close()
    pool.join()
    shutdown_manager(manager, event, thread_abort)

    if exception:
        raise exception

    return data_out


def wait_for_result(
    result: mp.pool.AsyncResult | Result,
    pool: NonDaemonicPool | FakePool,
) -> Any:  # noqa: ANN401
    """Wait for a worker result while watching for crashed worker processes.

    ``multiprocessing.pool.Pool`` silently replaces a worker process that died
    (e.g. killed by a signal) and the task it was processing is lost, so a
    plain ``result.get()`` would block forever.

    Args:
        result (mp.pool.AsyncResult | Result): The result to wait for.
        pool (NonDaemonicPool | FakePool): The pool that computes the result.

    Raises:
        WorkerProcessError: If a worker process of the pool died.

    Returns:
        Any: The result of the worker function.
    """
    while not result.ready():
        result.wait(WORKER_POLL_INTERVAL)
        if result.ready():
            break
        crashed = pool.crashed_workers()
        if crashed:
            raise WorkerProcessError(
                "Worker process(es) died unexpectedly: "
                + ", ".join(
                    f"{proc.name} ({describe_exitcode(proc.exitcode)})"
                    for proc in crashed
                )
            )
    return result.get()


def describe_exitcode(exitcode: int) -> str:
    """Return a human readable description of a process exit code.

    Args:
        exitcode (int): The exit code of the process. Negative values are the
            number of the signal that terminated the process.

    Returns:
        str: The description of the exit code.
    """
    if exitcode < 0:
        import signal

        try:
            return f"killed by {signal.Signals(-exitcode).name}"
        except ValueError:
            return f"killed by signal {-exitcode}"
    return f"exit code {exitcode}"


def shutdown_manager(
    manager: None | multiprocessing.Manager,
    event: None | threading.Event,
    thread_abort: None | threading.Thread,
) -> None:
    """Shutdown the manager and restore the original abort event.

    Args:
        manager (None | multiprocessing.Manager): The manager used for
            inter-process communication.
        event (None | threading.Event): The original event from thread_abort.
        thread_abort (None | threading.Thread): The thread with the event
            attribute.
    """
    if not manager:
        return
    # Need to shutdown manager so it doesn't hold files in use
    if event:
        # Restore original event
        if thread_abort.event.is_set():
            event.set()
        thread_abort.event = event
    manager.shutdown()


class WorkerFunc:
    """Wrap 'func' with optional arguments.

    Args:
        func (Callable): The function to wrap.
        exit_ (bool, optional): If True, the worker process will exit after
            processing the data. This is useful for cleaning up resources in
            worker processes, especially on Windows where atexit handlers may
            not run automatically.
    """

    def __init__(self, func: Callable, exit_: bool = False) -> None:
        self.func = func
        self.exit = exit_

    def __call__(
        self,
        data: Iterable,
        thread_abort_event: threading.Event,
        progress_queue: mp.Queue,
        *args,
        **kwds,
    ) -> Any | Exception:  # noqa: ANN401
        """Call the wrapped function with the given data and arguments.

        Args:
            data (Iterable): The data to process.
            thread_abort_event (threading.Event): Event to signal thread abort.
            progress_queue (multiprocessing.Queue): Queue to send progress updates.
            *args: Positional arguments to pass to the wrapped function.
            **kwds: Keyword arguments to pass to the wrapped function.

        Returns:
            Exception | result: The result of the function call, or an exception
                if one occurred.
        """
        try:
            return self.func(data, thread_abort_event, progress_queue, *args, **kwds)
        except Exception as exception:
            if (
                not getattr(sys, "_sigbreak", False)
                or not isinstance(exception, IOError)
                or exception.args[0] != errno.EPIPE
            ):
                import traceback

                print(traceback.format_exc())
            return exception
        finally:
            progress_queue.put(EOFError())
            if mp.current_process().name != "MainProcess":
                print("Exiting worker process", mp.current_process().name)
                if sys.platform == "win32" and self.exit:
                    # Exit handlers registered with atexit will not normally
                    # run when a multiprocessing subprocess exits. We are only
                    # interested in our own exit handler though.
                    # Note all of this only applies to Windows, as it doesn't
                    # have fork().

                    # This is not working with Ptyhon 3 as atexit is reimplemented in C
                    # and atexit._exithandlers are not available.
                    # for func, targs, kargs in atexit._exithandlers:
                    #     # Find our lockfile removal exit handler
                    #     if (
                    #         targs
                    #         and isinstance(targs[0], str)
                    #         and targs[0].endswith(".lock")
                    #     ):
                    #         print("Removing lockfile", targs[0])
                    #         try:
                    #             func(*targs, **kargs)
                    #         except Exception as exception:
                    #             print("Could not remove lockfile:", exception)

                    # Logging is normally shutdown by atexit, as well. Do
                    # it explicitly instead.
                    logging.shutdown()


class Mapper:
    """Wrap 'func' with optional arguments.

    To be used as function argument for Pool.map

    Args:
        func (Callable): The function to wrap.
        *args: Positional arguments to pass to the wrapped function.
        **kwds: Keyword arguments to pass to the wrapped function.
    """

    def __init__(self, func: Callable, *args, **kwds) -> None:
        self.func = WorkerFunc(func)
        self.args = args
        self.kwds = kwds

    def __call__(self, iterable: Iterable) -> list:
        """Call the wrapped function with the given iterable.

        Args:
            iterable (Iterable): The iterable to process with the wrapped function.

        Returns:
            list: The result of applying the wrapped function to the iterable.
        """
        return self.func(iterable, *self.args, **self.kwds)


class NonDaemonicProcess(MP_CONTEXT.Process):
    """Process that is not daemonic.

    This is needed for Windows, as daemonic processes cannot have
    children. This is a problem when using multiprocessing.Pool,
    as the worker processes are daemonic and they create child
    processes when they call the function.
    """

    @property
    def daemon(self) -> bool:
        """Return False, as this process is always non-daemonic.

        Returns:
            bool: Always False, indicating that this process is non-daemonic.
        """
        return False

    @daemon.setter
    def daemon(self, daemonic: bool) -> None:
        """Set the process as non-daemonic.

        Args:
            daemonic (bool): This is ignored, as this process is always
                non-daemonic.
        """
        return


class NonDaemonicPool(mp.pool.Pool):
    """Pool that has non-daemonic workers, always using the "spawn" context."""

    def __init__(self, *args, **kwargs) -> None:
        # Every worker process ever started by this pool. The pool itself
        # forgets about worker processes that exited.
        self._all_workers = []
        kwargs.setdefault("context", MP_CONTEXT)
        super().__init__(*args, **kwargs)

    def crashed_workers(self) -> list[NonDaemonicProcess]:
        """Return the worker processes that exited while the pool was running.

        Workers only exit when the pool is closed or terminated (there is no
        ``maxtasksperchild`` limit), so any worker with a non-zero exit code
        died unexpectedly.

        Returns:
            list[NonDaemonicProcess]: The crashed worker processes.
        """
        return [proc for proc in self._all_workers if proc.exitcode not in (None, 0)]

    def Process(self, *args, **kwargs) -> NonDaemonicProcess:  # noqa: N802
        """Return a non-daemonic process.

        This is needed for Windows, as daemonic processes cannot have
        children. This is a problem when using multiprocessing.Pool,
        as the worker processes are daemonic and they create child
        processes when they call the function.

        Returns:
            NonDaemonicProcess: A non-daemonic process.
        """
        # Process is a function after Python 3.7+
        # Process = NonDaemonicProcess -- This will not work with Python3.7+
        proc = super().Process(*args, **kwargs)
        proc.__class__ = NonDaemonicProcess  # TODO: This is not cool, find a better way
        #                                            of doing it.
        self._all_workers.append(proc)
        return proc


class FakeManager:
    """Fake manager."""

    def Queue(self) -> FakeQueue:  # noqa: N802
        """Return a fake queue.

        Returns:
            FakeQueue: A fake queue that does not use multiprocessing.
        """
        return FakeQueue()

    def Value(self, typecode: str, *args, **kwds) -> mp.managers.Value:  # noqa: N802
        """Return a fake Value.

        Args:
            typecode (str): The type code for the value.
            *args: Positional arguments to pass to the Value constructor.
            **kwds: Keyword arguments to pass to the Value constructor.

        Returns:
            mp.managers.Value: A fake Value that does not use multiprocessing.
        """
        return mp.managers.Value(typecode, *args, **kwds)

    def shutdown(self) -> None:
        """Shutdown the fake manager."""


class FakePool:
    """Fake pool.

    This is a fake pool that does not use multiprocessing. It is used for
    testing purposes or when multiprocessing is not available or not needed.
    It does not create worker processes and runs the function in the main
    thread. It is a drop-in replacement for multiprocessing.Pool.
    It does not support any of the advanced features of multiprocessing.Pool,
    such as process management, task tracking, or error handling.
    It is only suitable for simple use cases where the function can be run
    synchronously in the main thread without any parallelism.

    Args:
        processes (None | int, optional): Number of worker processes to use.
            Not used in this fake pool.
        initializer (None | callable, optional): Function to run when a worker
            process starts. Not used in this fake pool.
        initargs (tuple, optional): Arguments to pass to the initializer
            function. Not used in this fake pool.
        maxtasksperchild (None | int, optional): Maximum number of tasks a
            worker can complete before it is replaced. Not used in this fake
            pool.
    """

    def __init__(
        self,
        processes: None | int = None,
        initializer: None | Callable = None,
        initargs: tuple = (),
        maxtasksperchild: None | int = None,
    ) -> None:
        pass

    def apply_async(self, func: Callable, args: tuple, kwds: dict) -> Result:
        """Apply function asynchronously.

        Args:
            func (Callable): The function to apply.
            args (tuple): The positional arguments to pass to the function.
            kwds (dict): The keyword arguments to pass to the function.

        Returns:
            Result: A Result instance containing the result of the function call.
        """
        return Result(func(*args, **kwds))

    def close(self) -> NonDaemonicPool:
        """Close the pool."""

    def join(self) -> None:
        """Wait for the worker processes to finish."""

    def map(
        self, func: Callable, iterable: Iterable, chunksize: None | int = None
    ) -> list:
        """Map function over iterable using the given function.

        Args:
            func (Callable): The function to apply to each item in the
                iterable.
            iterable (Iterable): The iterable to process.
            chunksize (None | int, optional): The size of each chunk to
                process. Not used in this fake pool.

        Returns:
            list: A list of results from applying the function to each item
                in the iterable.
        """
        return func(iterable)

    def terminate(self) -> None:
        """Terminate the pool."""

    def crashed_workers(self) -> list:
        """Return the crashed worker processes.

        Returns:
            list: Always empty, there are no worker processes.
        """
        return []


class FakeQueue:
    """Fake queue."""

    def __init__(self) -> None:
        self.queue = []

    def get(self, block: bool = True, timeout: None | float = None) -> None | Any:  # noqa: ANN401
        """Get an item from the queue.

        Args:
            block (bool): If True, block until an item is available.
            timeout (None | float): Timeout for blocking, not used in this fake
                queue.

        Raises:
            Empty: If the queue is empty.

        Returns:
            None | Any: The item from the queue, or None if the queue is empty.
        """
        try:
            return self.queue.pop()
        except Exception as e:
            raise Empty from e

    def join(self) -> None:
        """Wait until all items in the queue have been processed."""

    def put(self, item: Any, block: bool = True, timeout: None | float = None) -> None:  # noqa: ANN401
        """Put an item into the queue.

        Args:
            item (Any): The item to be added to the queue.
            block (bool): If True, block until the item is added.
            timeout (None | float): Timeout for blocking, not used in this fake
                queue.
        """
        self.queue.append(item)


class Result:
    """Result proxy.

    Args:
        result (Any): The result to be returned by the get() method.
    """

    def __init__(self, result: Any) -> None:  # noqa: ANN401
        self.result = result

    def get(self) -> WorkerFunc:
        """Return result.

        Returns:
            WorkerFunc: WorkerFunc instance as the result.
        """
        return self.result

    def ready(self) -> bool:
        """Return whether the result is available.

        Returns:
            bool: Always True, the result is computed synchronously.
        """
        return True

    def wait(self, timeout: None | float = None) -> None:
        """Wait for the result, which is always available already.

        Args:
            timeout (None | float): Not used.
        """
