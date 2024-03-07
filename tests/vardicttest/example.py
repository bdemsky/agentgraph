import agentgraph
import os
import time


def testFunc1(scheduler, val) -> list:
    print("testFunc1 start")
    time.sleep(0.1)
    print("testFunc1 end")
    return [val+1]

def testFunc2(scheduler, d: dict) -> list:
    print(d)
    return []

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
varmap = agentgraph.VarMap()
var = varmap.mapToInt()
vardict = agentgraph.VarDict()

for i in range(30):
    nvar = scheduler.runPythonAgent(testFunc1, numOuts = 1, pos=[var], vmap = varmap)
    varmap = None
    vardict[i+1] = nvar
    var = nvar

scheduler.runPythonAgent(testFunc2, pos=[vardict])


scheduler.shutdown()
