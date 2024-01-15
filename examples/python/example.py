import agentgraph
import os
import time


def testFunc1(scheduler, foo: int) -> list:
    print("TestA", foo)
    return []

def testFunc2(scheduler, bar: int) -> list:
    print("TestB", bar)
    return []

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
vmap = agentgraph.VarMap()
var = vmap.mapToInt("test", 3)
scheduler.runPythonAgent(testFunc1, pos=[var], vmap=vmap)
scheduler.runPythonAgent(testFunc2, pos=[var])
scheduler.shutdown()
