import agentgraph
import os
import time


async def testFunc1(scheduler, foo: int) -> dict:
    print("TestA", foo)
    return dict()

async def testFunc2(scheduler, bar: int) -> dict:
    print("TestB", bar)
    return dict()

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
vmap = agentgraph.VarMap()
var = vmap.mapToInt("test", 3)
agentpair = agentgraph.createPythonAgent(testFunc1, pos=[var]) | agentgraph.createPythonAgent(testFunc2, pos=[var])
scheduler.addTask(agentpair.start, vmap)
scheduler.shutdown()
