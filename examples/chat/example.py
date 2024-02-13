import agentgraph
import os
import time


model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
prompts = agentgraph.Prompts("./examples/chat/prompts/")

sysA = prompts.loadPrompt("SystemA")
sysB = prompts.loadPrompt("SystemB")
pA = prompts.loadPrompt("PromptA")
ovarA = agentgraph.Var("OutA")
ovarB = agentgraph.Var("OutB")
varmap = agentgraph.VarMap()
convA = varmap.mapToConversation("AgentA")
convB = varmap.mapToConversation("AgentB")

for i in range(2):
    scheduler.runLLMAgent(ovarA, conversation = convA, msg = convA > (convA & pA | sysA ** pA), vmap = varmap)
    varmap = None
    scheduler.runLLMAgent(ovarB, conversation = convB, msg = convB > (convB & ovarA | sysB ** ovarA))
    
print("Tasks Enqueued")
print(ovarA.getValue())
print("-----")
print(ovarB.getValue())

scheduler.shutdown() 
