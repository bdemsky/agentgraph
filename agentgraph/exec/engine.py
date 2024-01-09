import asyncio
import janus
import traceback
import sys
import concurrent.futures

from threading import Thread
from agentgraph.core.graph import GraphNode, GraphPair, GraphNested, VarMap

class Engine:
    def __init__(self, concurrency: int = 20):
        self.loop = asyncio.new_event_loop()
        self.event_loop_thread = Thread(target=self.run_event_loop)
        self.event_loop_thread.start()
        future = asyncio.run_coroutine_threadsafe(create_queue(), self.loop)
        self.queue = future.result()
        self.concurrency = concurrency
        self.threadPool = concurrent.futures.ThreadPoolExecutor(max_workers = concurrency)
        for i in range(concurrency):
            asyncio.run_coroutine_threadsafe(self.worker(i), self.loop)
        
    def run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def worker(self, i):
        import agentgraph.exec.scheduler
        lastscheduler = None

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
                scheduler.completed(scheduleNode)
            except Exception as e:
                print('Error', e)
                print(traceback.format_exc())

            self.queue.async_q.task_done()

    def runScan(self, graph: GraphNode, scheduler: 'agentgraph.exec.scheduler.Scheduler'):
        asyncio.run_coroutine_threadsafe(wrap_scan(scheduler, graph), self.loop).result()
        return

    def queueItem(self, node: 'agentgraph.exec.scheduler.ScheduleNode', scheduler):
        self.queue.async_q.put_nowait((node, scheduler))

    def threadQueueItem(self, node: 'agentgraph.exec.scheduler.ScheduleNode', scheduler):
        self.threadPool.submit(threadrun, self, node, scheduler)
        
    def shutdown(self):
        self.threadPool.shutdown(wait=True)
        self.queue.sync_q.join()
        for i in range(self.concurrency):
            self.queue.sync_q.put(None)
        self.queue.sync_q.join()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.event_loop_thread.join()

def threadrun(engine, scheduleNode, scheduler):
    import agentgraph.exec.scheduler
    agentgraph.exec.scheduler.setCurrentTask(scheduleNode)
    agentgraph.exec.scheduler.setCurrentScheduler(scheduler)
    try:
        scheduleNode.threadRun(scheduler)
        asyncio.run_coroutine_threadsafe(wrap_completed(scheduler, scheduleNode), engine.loop).result()
    except Exception as e:
        print('Error', e)
        print(traceback.format_exc())

async def wrap_completed(scheduler: 'agentgraph.exec.scheduler.Scheduler', scheduleNode):
    scheduler.completed(scheduleNode)
        
async def wrap_scan(scheduler: 'agentgraph.exec.scheduler.Scheduler', graph: GraphNode):
    scheduler.scan(graph)
    
async def create_queue() -> janus.Queue:
    queue = janus.Queue()
    return queue
            
