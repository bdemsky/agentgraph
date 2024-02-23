import agentgraph
import os
import time


def testFunc1(scheduler) -> list:
    prompts = agentgraph.Prompts("./examples/pythonchild/prompts/")
    sys = prompts.loadPrompt("System")
    pA = prompts.loadPrompt("PromptA")
    ovarA = scheduler.runLLMAgent(msg = sys ** pA)
    ovarR = ovarA
    
    for i in range(3):
        pB = prompts.loadPrompt("PromptB", {'Recipe': ovarR})
        ovarB = scheduler.runLLMAgent(msg = sys ** pB)
        ovarR = ovarB

    print("Tasks Enqueued")
    print(ovarA.getValue())
    return []

def testFunc2(scheduler, bar: int) -> list:
    print("TestB", bar)
    return []

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
scheduler.runPythonAgent(testFunc1)
scheduler.runPythonAgent(testFunc2, pos=[3])
scheduler.shutdown()
