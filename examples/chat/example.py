import agentgraph
import os
import time


model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
prompts = agentgraph.Prompts("./examples/chat/prompts/")

sysA = prompts.loadPrompt("SystemA")
sysB = prompts.loadPrompt("SystemB")
pA = prompts.loadPrompt("PromptA")
convA = agentgraph.Conversation()
convB = agentgraph.Conversation()
varmap = agentgraph.VarMap()
ovarB = varmap.mapToNone()

for i in range(2):
    ovarA = scheduler.runLLMAgent(conversation = convA, msg = convA > (convA & ovarB | sysA ** pA), vmap = varmap)
    varmap = None
    ovarB = scheduler.runLLMAgent(conversation = convB, msg = convB > (convB & ovarA | sysB ** ovarA))
    
print("Tasks Enqueued")
print(ovarA.getValue())
print("-----")
print(ovarB.getValue())

scheduler.shutdown() 
