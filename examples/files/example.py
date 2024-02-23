import agentgraph
import os
import time


def testFunc1(scheduler, fs) -> list:
    fs["a"] = fs["a"] + "1"
    return [3]

def testFunc2(scheduler, fs) -> list:
    fs["a"] = fs["a"] + "2"
    return [4]

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
fs = agentgraph.FileStore()
fs["a"]="0"
vara = scheduler.runPythonAgent(testFunc1, pos=[fs], outTypes = [agentgraph.VarType])
varb = scheduler.runPythonAgent(testFunc2, pos=[fs], outTypes = [agentgraph.VarType])

print(fs["a"])
print(vara.getValue())
print(varb.getValue())

scheduler.shutdown()
