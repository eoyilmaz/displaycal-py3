"""Utilities for parallel processing with multiprocessing.

It includes functions and classes to manage worker pools, handle task
distribution, and process data slices efficiently.
"""

import contextlib
import errno
import logging
import math
import multiprocessing as mp
import multiprocessing.pool
import sys
import threading
from queue import Empty


def cpu_count(limit_by_total_vmem=True):
    """Return the number of CPUs in the system.

    If psutil is installed, the number of reported CPUs is limited according to
    total RAM by assuming 1 GB for each CPU + 1 GB for the system, unless
    limit_by_total_vmem is False, to allow a reasonable amount of memory for
    each CPU.

    Return fallback value of 1 if CPU count cannot be determined.

    """
    max_cpus = sys.maxsize
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
                max_cpus = int(psutil.virtual_memory().total / (1024**3) - 1)
    try:
        return max(min(mp.cpu_count(), max_cpus), 1)
    except Exception:
        return 1


def pool_slice(
    func,
    data_in,
    args=None,
    kwds=None,
    num_workers=None,
    thread_abort=None,
    logfile=None,
    num_batches=1,
    progress=0,
):
    """Process data in slices using a pool of workers and return the results.

    The individual worker results are returned in the same order as the
    original input data, irrespective of the order in which the workers
    finished (FIFO).

    Progress percentage is written to optional logfile using a background
    thread that monitors a queue.
    Note that 'func' is supposed to periodically check thread_abort.event
    which is passed as the first argument to 'func', and put its progress
    percentage into the queue which is passed as the second argument to 'func'.

    """
    if args is None:
        args = ()

    if kwds is None:
        kwds = {}

    from DisplayCAL.config import getcfg

    if num_workers is None:
        num_workers = cpu_count()
    num_workers = max(min(int(num_workers), len(data_in)), 1)
    max_workers = getcfg("multiprocessing.max_cpus")
    if max_workers:
        num_workers = min(num_workers, max_workers)

    if num_workers == 1 or not num_batches:
        # Splitting the workload into batches only makes sense if there are
        # multiple workers
        num_batches = 1

    chunksize = float(len(data_in)) / (num_workers * num_batches)
    if chunksize < 1:
        num_batches = 1
        chunksize = float(len(data_in)) / num_workers

    if num_workers > 1:
        Pool = NonDaemonicPool
        manager = mp.Manager()
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
        Queue = manager.Queue
    else:
        # Do it all in in the main thread of the current instance
        Pool = FakePool
        manager = None
        Queue = FakeQueue

    thread_abort_event = thread_abort.event if thread_abort is not None else None
    progress_queue = Queue()
    if logfile:

        def progress_logger(num_workers, progress=0.0):
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

        threading.Thread(
            target=progress_logger,
            args=(num_workers * num_batches, progress * num_workers * num_batches),
            name="ProcessProgressLogger",
            group=None,
        ).start()

    pool = Pool(num_workers)
    results = []
    start = 0
    for batch in range(num_batches):
        for i in range(batch * num_workers, (batch + 1) * num_workers):
            end = math.ceil(chunksize * (i + 1))
            results.append(
                pool.apply_async(
                    WorkerFunc(func, batch == num_batches - 1),
                    (data_in[start:end], thread_abort_event, progress_queue, *args),
                    kwds,
                )
            )
            start = end

    # Get results
    exception = None
    data_out = []
    for result in results:
        result = result.get()
        if isinstance(result, Exception):
            exception = result
            continue
        data_out.append(result)

    pool.close()
    pool.join()

    if manager:
        # Need to shutdown manager so it doesn't hold files in use
        if event:
            # Restore original event
            if thread_abort.event.is_set():
                event.set()
            thread_abort.event = event
        manager.shutdown()

    if exception:
        raise exception

    return data_out


class WorkerFunc:
    """Wrap 'func' with optional arguments.

    Args:
        func (callable): The function to wrap.
        exit_ (bool): If True, the worker process will exit after processing
            the data. This is useful for cleaning up resources in worker
            processes, especially on Windows where atexit handlers may not run
            automatically.
    """

    def __init__(self, func, exit_=False):
        self.func = func
        self.exit = exit_

    def __call__(self, data, thread_abort_event, progress_queue, *args, **kwds):
        """Call the wrapped function with the given data and arguments.

        Args:
            data (iterable): The data to process.
            thread_abort_event (threading.Event): Event to signal thread abort.
            progress_queue (multiprocessing.Queue): Queue to send progress updates.
            *args: Positional arguments to pass to the wrapped function.
            **kwds: Keyword arguments to pass to the wrapped function.

        Returns:
            Exception or result: The result of the function call, or an exception
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
        func (callable): The function to wrap.
        *args: Positional arguments to pass to the wrapped function.
        **kwds: Keyword arguments to pass to the wrapped function.
    """

    def __init__(self, func, *args, **kwds):
        self.func = WorkerFunc(func)
        self.args = args
        self.kwds = kwds

    def __call__(self, iterable):
        """Call the wrapped function with the given iterable.

        Args:
            iterable (iterable): The iterable to process with the wrapped function.

        Returns:
            list: The result of applying the wrapped function to the iterable.
        """
        return self.func(iterable, *self.args, **self.kwds)


class NonDaemonicProcess(mp.Process):
    """Process that is not daemonic.

    This is needed for Windows, as daemonic processes cannot have
    children. This is a problem when using multiprocessing.Pool,
    as the worker processes are daemonic and they create child
    processes when they call the function.
    """

    @property
    def daemon(self):
        """Return False, as this process is always non-daemonic.

        Returns:
            bool: Always False, indicating that this process is non-daemonic.
        """
        return False

    @daemon.setter
    def daemon(self, daemonic):
        """Set the process as non-daemonic.

        Args:
            daemonic (bool): This is ignored, as this process is always
                non-daemonic.
        """
        return


class NonDaemonicPool(mp.pool.Pool):
    """Pool that has non-daemonic workers"""

    def Process(self, *args, **kwargs):
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
        return proc


class FakeManager:
    """Fake manager."""

    def Queue(self):
        """Return a fake queue.

        Returns:
            FakeQueue: A fake queue that does not use multiprocessing.
        """
        return FakeQueue()

    def Value(self, typecode, *args, **kwds):
        """Return a fake Value.

        Args:
            typecode (str): The type code for the value.
            *args: Positional arguments to pass to the Value constructor.
            **kwds: Keyword arguments to pass to the Value constructor.

        Returns:
            mp.managers.Value: A fake Value that does not use multiprocessing.
        """
        return mp.managers.Value(typecode, *args, **kwds)

    def shutdown(self):
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
        processes (int, optional): Number of worker processes to use. Not used
            in this fake pool.
        initializer (callable, optional): Function to run when a worker process
            starts. Not used in this fake pool.
        initargs (tuple, optional): Arguments to pass to the initializer
            function. Not used in this fake pool.
        maxtasksperchild (int, optional): Maximum number of tasks a worker can
            complete before it is replaced. Not used in this fake pool.
    """

    def __init__(
        self, processes=None, initializer=None, initargs=(), maxtasksperchild=None
    ):
        pass

    def apply_async(self, func, args, kwds):
        """Apply function asynchronously.

        Args:
            func (callable): The function to apply.
            args (tuple): The positional arguments to pass to the function.
            kwds (dict): The keyword arguments to pass to the function.

        Returns:
            Result: A Result instance containing the result of the function call.
        """
        return Result(func(*args, **kwds))

    def close(self):
        """Close the pool."""

    def join(self):
        """Wait for the worker processes to finish."""

    def map(self, func, iterable, chunksize=None):
        """Map function over iterable using the given function.

        Args:
            func (callable): The function to apply to each item in the
                iterable.
            iterable (iterable): The iterable to process.
            chunksize (int, optional): The size of each chunk to process. Not
                used in this fake pool.

        Returns:
            list: A list of results from applying the function to each item
                in the iterable.
        """
        return func(iterable)

    def terminate(self):
        """Terminate the pool."""


class FakeQueue:
    """Fake queue."""

    def __init__(self):
        self.queue = []

    def get(self, block=True, timeout=None):
        """Get an item from the queue.

        Args:
            block (bool): If True, block until an item is available.
            timeout (float): Timeout for blocking, not used in this fake queue.

        Raises:
            Empty: If the queue is empty.
        """
        try:
            return self.queue.pop()
        except Exception as e:
            raise Empty from e

    def join(self):
        """Wait until all items in the queue have been processed."""

    def put(self, item, block=True, timeout=None):
        """Put an item into the queue.

        Args:
            item: The item to be added to the queue.
            block (bool): If True, block until the item is added.
            timeout (float): Timeout for blocking, not used in this fake queue.
        """
        self.queue.append(item)


class Result:
    """Result proxy."""

    def __init__(self, result):
        self.result = result

    def get(self):
        """Return result.

        Returns:
            WorkerFunc: WorkerFunc instance as the result.
        """
        return self.result
