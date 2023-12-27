import asyncio
import janus
import traceback
import sys

from threading import Thread
from agentgraph.graph.Graph import GraphPair, GraphNested

class Engine:
    def __init__(self, concurrency: int = 20):
        self.loop = asyncio.new_event_loop()
        self.event_loop_thread = Thread(target=self.run_event_loop)
        self.event_loop_thread.start()
        future = asyncio.run_coroutine_threadsafe(create_queue(), self.loop)
        self.queue = future.result()
        self.concurrency = concurrency
        
        for i in range(concurrency):
            asyncio.run_coroutine_threadsafe(self.worker(i), self.loop)
        
    def run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def worker(self, i):
        while True:
            item = await self.queue.async_q.get()
            if item == None:
                self.queue.async_q.task_done()
                break
            scheduleNode, scheduler = item
            try:
                await scheduleNode.run()
            except Exception as e:
                print('Error', e)
                print(traceback.format_exc())
            scheduler.completed(scheduleNode)
            self.queue.async_q.task_done()

    def runGraph(self, graph: GraphNested, inVars: dict):
        from agentgraph.exec.Scheduler import Scheduler
        scheduler = Scheduler(graph, inVars, None, self)
        asyncio.run_coroutine_threadsafe(wrap_scan(scheduler, graph), self.loop).result()
        return

    def queueItem(self, node: 'agentgraph.graph.ScheduleNode', scheduler):
        self.queue.async_q.put_nowait((node, scheduler))
        
    def shutdown(self):
        self.queue.sync_q.join()
        for i in range(self.concurrency):
            self.queue.sync_q.put(None)
        self.queue.sync_q.join()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.event_loop_thread.join()

async def wrap_scan(scheduler, graph):
    scheduler.scan(graph.start)

async def create_queue() -> janus.Queue:
    queue = janus.Queue()
    return queue
            
