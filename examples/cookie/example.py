import agentgraph
import os
import time


model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
prompts = agentgraph.Prompts("./examples/cookie/prompts/")

sys = prompts.loadPrompt("System")
ovarA = agentgraph.Var()
pA = prompts.loadPrompt("PromptA")
scheduler.runLLMAgent(ovarA, msg = sys ** pA)
ovarR = ovarA

for i in range(3):
    pB = prompts.loadPrompt("PromptB", { 'Recipe': ovarR})
    ovarB = agentgraph.Var()
    scheduler.runLLMAgent(ovarB, msg = sys ** pB)
    ovarR = ovarB
    
print("Tasks Enqueued")
print(ovarA.getValue())
print("-----")
print(ovarB.getValue())

scheduler.shutdown() 
