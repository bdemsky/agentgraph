import asyncio
import janus
from threading import Thread

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
            await scheduleNode.run()
            await scheduler.completed(scheduleNode)
            self.queue.async_q.task_done()
            
    def queueItem(self, node: 'agentgraph.graph.ScheduleNode', scheduler):
        self.queue.sync_q.put((node, scheduler))

    def shutdown(self):
        for i in range(self.concurrency):
            self.queue.sync_q.put(None)
        self.queue.sync_q.join()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.event_loop_thread.join()
        
async def create_queue() -> janus.Queue:
    queue = janus.Queue()
    return queue
            
