import agentgraph
import os
import time
from agentgraph.core.mutable import Mutable


def testFuncA1(scheduler, m, start) -> list:
    time.sleep(0.5)
    print("TestA", time.time() - start)
    time.sleep(0.5)
    return []

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
start = time.time()

mutable = Mutable()
snapshot = Mutable(mutable)
snapshot._readonly = True
print('START')
scheduler.runPythonAgent(testFuncA1, pos=[snapshot, start])
scheduler.runPythonAgent(testFuncA1, pos=[snapshot, start])
scheduler.runPythonAgent(testFuncA1, pos=[mutable, start])
scheduler.runPythonAgent(testFuncA1, pos=[snapshot, start])
scheduler.runPythonAgent(testFuncA1, pos=[snapshot, start])
snapshot.waitForAccess()
print("TestB", time.time() - start)
scheduler.shutdown()