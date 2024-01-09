import agentgraph
import os
import time


def testFunc1(scheduler) -> dict:
    print(scheduler)
    prompts = agentgraph.Prompts("./examples/pythonchild/prompts/")
    sys = prompts.createPrompt("System")
    g = agentgraph.VarMap()
    ovarA = agentgraph.Var("Recipe")
    pA = prompts.createPrompt("PromptA")
    agentA = agentgraph.createLLMAgent(ovarA, msg = sys > pA)
    scheduler.addTask(agentA.start, g)
    ovarR = ovarA
    print("START")
    
    for i in range(3):
        pB = prompts.createPrompt("PromptB", {ovarR})
        gnew = agentgraph.VarMap()
        ovarB = agentgraph.Var("Recipe")
        agentB = agentgraph.createLLMAgent(ovarB, msg = sys > pB)
        scheduler.addTask(agentB.start, gnew)
        ovarR = ovarB

    print("Tasks Enqueued")
    print(ovarA.getValue())

    return dict()

def testFunc2(scheduler, bar: int) -> dict:
    print(scheduler)
    print("TestB", bar)
    return dict()

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
print(scheduler)
vmap = agentgraph.VarMap()
var = vmap.mapToInt("test", 3)
agentpair = agentgraph.createPythonAgent(testFunc1) | agentgraph.createPythonAgent(testFunc2, pos=[var])
scheduler.addTask(agentpair.start, vmap)
scheduler.shutdown()
