import agentgraph
import os
import time


model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
prompts = agentgraph.Prompts("./examples/cookie/prompts/")

sys = prompts.createPrompt("System")
g = agentgraph.VarMap()
ovarA = agentgraph.Var("Recipe")
pA = prompts.createPrompt("PromptA")
agentA = agentgraph.createLLMAgent(None, ovarA, msg = sys > pA)
scheduler.addTask(agentA.start, g)
ovarR = ovarA

for i in range(2):
    pB = prompts.createPrompt("PromptB", {ovarR})
    gnew = agentgraph.VarMap()
    ovarB = agentgraph.Var("Recipe")
    agentB = agentgraph.createLLMAgent(None, ovarB, msg = sys > pB)
    scheduler.addTask(agentB.start, gnew)
    ovarR = ovarB
    
print("Tasks Enqueued")
print(ovarA.getValue())
print("-----")
print(ovarB.getValue())

scheduler.shutdown() 
