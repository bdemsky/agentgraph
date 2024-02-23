import agentgraph
import os
import time


def testFunc1(scheduler, val) -> list:
    print("testFunc1 start")
    time.sleep(0.1)
    print("testFunc1 end")
    return [val+1]

def testFunc2(scheduler, s: set) -> list:
    print(s)
    return []

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
varmap = agentgraph.VarMap()
var = varmap.mapToInt()
varset = agentgraph.VarSet()

for i in range(30):
    nvar = scheduler.runPythonAgent(testFunc1, outTypes = [agentgraph.VarType], pos=[var], vmap = varmap)
    varmap = None
    varset.add(nvar)
    var = nvar

scheduler.runPythonAgent(testFunc2, pos=[varset])


scheduler.shutdown()
