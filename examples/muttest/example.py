import agentgraph
import os
import time


def testFunc1(scheduler, fs) -> list:
    print("testFunc1 start")
    time.sleep(2)
    print("testFunc1 end")
    return []

def testFunc2(scheduler, fs) -> list:
    print("testFunc2 start (should appear only after testFunc1 ends)")
    print("testFunc2 end")
    return []

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
fs = agentgraph.FileStore()
fs["a"]="0"
scheduler.runPythonAgent(testFunc1, pos=[fs])
scheduler.runPythonAgent(testFunc2, pos=[fs])

print(fs["a"])

scheduler.shutdown()
