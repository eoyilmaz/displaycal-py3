# -*- coding: utf-8 -*-

from queue import Empty
import atexit
import errno
import logging
import math
import multiprocessing as mp
import multiprocessing.pool
import sys
import threading


def cpu_count(limit_by_total_vmem=True):
    """Returns the number of CPUs in the system

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
            try:
                max_cpus = int(psutil.virtual_memory().total / (1024**3) - 1)
            except Exception:
                pass
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

    if thread_abort is not None:
        thread_abort_event = thread_abort.event
    else:
        thread_abort_event = None

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
                except IOError:
                    break
                except EOFError:
                    eof_count += 1
                    if eof_count == num_workers:
                        break
                perc = round(progress / num_workers)
                if perc > prevperc:
                    logfile.write("\r%i%%" % perc)
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
            end = int(math.ceil(chunksize * (i + 1)))
            results.append(
                pool.apply_async(
                    WorkerFunc(func, batch == num_batches - 1),
                    (data_in[start:end], thread_abort_event, progress_queue) + args,
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


class WorkerFunc(object):
    def __init__(self, func, exit=False):
        self.func = func
        self.exit = exit

    def __call__(self, data, thread_abort_event, progress_queue, *args, **kwds):
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


class Mapper(object):
    """Wrap 'func' with optional arguments.

    To be used as function argument for Pool.map

    """

    def __init__(self, func, *args, **kwds):
        self.func = WorkerFunc(func)
        self.args = args
        self.kwds = kwds

    def __call__(self, iterable):
        return self.func(iterable, *self.args, **self.kwds)


class NonDaemonicProcess(mp.Process):
    @property
    def daemon(self):
        return False

    @daemon.setter
    def daemon(self, daemonic):
        return


class NonDaemonicPool(mp.pool.Pool):
    """Pool that has non-daemonic workers"""

    def Process(self, *args, **kwargs):
        # Process is a function after Python 3.7+
        # Process = NonDaemonicProcess -- This will not work with Python3.7+
        proc = super(NonDaemonicPool, self).Process(*args, **kwargs)
        proc.__class__ = NonDaemonicProcess  # TODO: This is not cool, find a better way
        #                                            of doing it.
        return proc


class FakeManager(object):
    """Fake manager"""

    def Queue(self):
        return FakeQueue()

    def Value(self, typecode, *args, **kwds):
        return mp.managers.Value(typecode, *args, **kwds)

    def shutdown(self):
        pass


class FakePool(object):
    """Fake pool."""

    def __init__(
        self, processes=None, initializer=None, initargs=(), maxtasksperchild=None
    ):
        pass

    def apply_async(self, func, args, kwds):
        return Result(func(*args, **kwds))

    def close(self):
        pass

    def join(self):
        pass

    def map(self, func, iterable, chunksize=None):
        return func(iterable)

    def terminate(self):
        pass


class FakeQueue(object):
    """Fake queue."""

    def __init__(self):
        self.queue = []

    def get(self, block=True, timeout=None):
        try:
            return self.queue.pop()
        except Exception:
            raise Empty

    def join(self):
        pass

    def put(self, item, block=True, timeout=None):
        self.queue.append(item)


class Result(object):
    """Result proxy."""

    def __init__(self, result):
        self.result = result

    def get(self):
        """Return result.

        Returns:
            WorkerFunc: WorkerFunc instance as the result.
        """
        return self.result
