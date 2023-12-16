import asyncio
from threading import Thread

class Engine:
    def __init__(self, concurrency: int = 20):
        self.loop = asynio.new_event_loop()
        self.event_loop_thread = Thread(target=self.run_event_loop)
        self.event_loop_thread.start()
        self.queue = asicio.Queue()
        
        for i in range(concurrency):
            asyncio.run_coroutine_threadsafe(self.worker(i), self.loop)
        
    def run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def worker(self, i):
        while True:
            scheduleNode, scheduler = await self.queue.get()
            if item == None:
                break
            await scheduleNode.run()
            await scheduler.completed(scheduleNode)
            
    def queueItem(self, node: 'agentgraph.graph.ScheduleNode', scheduler):
        self.queue.put_nowait((node, scheduler))
