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
vmap = agentgraph.VarMap()
fs = agentgraph.FileStore()
varfs = vmap.mapToMutable("test", fs)
vara = agentgraph.Var("A")
varb = agentgraph.Var("B")
fs["a"]="0"
scheduler.runPythonAgent(testFunc1, pos=[varfs], out=[vara], vmap = vmap)
scheduler.runPythonAgent(testFunc2, pos=[varfs], out=[varb])

print(fs["a"])
print(vara.getValue())
print(varb.getValue())

scheduler.shutdown()
