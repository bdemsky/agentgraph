import asyncio
import janus
import traceback
import sys
import concurrent.futures
import agentgraph.config

from threading import Thread, Lock
from agentgraph.core.graph import GraphNode, GraphPair, GraphNested, VarMap

class Engine:
    def __init__(self, concurrency: int = 0):
        self.loop = asyncio.new_event_loop()
        self.event_loop_thread = Thread(target=self.run_event_loop)
        self.event_loop_thread.start()
        future = asyncio.run_coroutine_threadsafe(create_queue(), self.loop)
        self.queue: janus.Queue = future.result()
        self.concurrency = concurrency if concurrency > 0 else agentgraph.config.THREAD_POOL_DEFAULT_SIZE
        self.threadPool = concurrent.futures.ThreadPoolExecutor(max_workers = self.concurrency)
        self.pendingPythonTaskLock = Lock()
        self.pendingPythonTaskCount = 0 # number of tasks pending in thread pool
        for i in range(self.concurrency):
            asyncio.run_coroutine_threadsafe(self.worker(i), self.loop)
        
    def run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def worker(self, i):
        import agentgraph.exec.scheduler
        lastscheduler = None
        agentgraph.exec.scheduler.setAsync(True)

        while True:
            item = await self.queue.async_q.get()
            if item == None:
                self.queue.async_q.task_done()
                break
            scheduleNode, scheduler = item
            agentgraph.exec.scheduler.setCurrentTask(scheduleNode)
            if scheduler != lastscheduler:
                agentgraph.exec.scheduler.setCurrentScheduler(scheduler)
                lastscheduler = scheduler
            try:
                await scheduleNode.run()

                while True:
                    if scheduler.lock.acquire(blocking=False):
                        break
                    # Yield to other tasks
                    await asyncio.sleep(0)
                try:
                    scheduler.completed(scheduleNode)
                finally:
                    scheduler.lock.release()
                    
            except Exception as e:
                print('Error', e)
                print(traceback.format_exc())

            self.queue.async_q.task_done()

    def queueItem(self, node: 'agentgraph.exec.scheduler.ScheduleNode', scheduler):
        isAsync = agentgraph.exec.scheduler.getAsync()
        if (isAsync):
            self.queue.async_q.put_nowait((node, scheduler))
        else:
            self.queue.sync_q.put((node, scheduler))

    def threadQueueItem(self, node: 'agentgraph.exec.scheduler.ScheduleNode', scheduler):
        with self.pendingPythonTaskLock:
            self.pendingPythonTaskCount += 1
        scheduler.future = self.threadPool.submit(threadrun, self, node, scheduler)
    
    def getPendingPythonTaskCount(self):
        """
        Get number of Python tasks still pending in thread pool
        """
        with self.pendingPythonTaskLock:
            return self.pendingPythonTaskCount
        
    def shutdown(self):
        self.threadPool.shutdown(wait=True)
        self.queue.sync_q.join()
        for i in range(self.concurrency):
            self.queue.sync_q.put(None)
        self.queue.sync_q.join()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.event_loop_thread.join()

def threadrun(engine, scheduleNode, scheduler):
    """
    Start a new thread to run child task.
    """

    with engine.pendingPythonTaskLock:
        engine.pendingPythonTaskCount -= 1

    import agentgraph.exec.scheduler
    agentgraph.exec.scheduler.setCurrentTask(scheduleNode)
    agentgraph.exec.scheduler.setCurrentScheduler(scheduler)
    try:
        scheduleNode.threadRun(scheduler)
        with scheduler.lock:
            scheduler.completed(scheduleNode)
    except Exception as e:
        print('Error', e)
        print(traceback.format_exc())

async def create_queue() -> janus.Queue:
    queue: janus.Queue = janus.Queue()
    return queue
            
