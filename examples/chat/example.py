import agentgraph
import os
import time


model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
prompts = agentgraph.Prompts("./examples/chat/prompts/")

sysA = prompts.createPrompt("SystemA")
sysB = prompts.createPrompt("SystemB")
pA = prompts.createPrompt("PromptA")
ovarA = agentgraph.Var("OutA")
ovarB = agentgraph.Var("OutB")
varmap = agentgraph.VarMap()
convA = varmap.mapToConversation("AgentA")
convB = varmap.mapToConversation("AgentB")

for i in range(2):
    agentA = agentgraph.createLLMAgent(ovarA, conversation = convA, msg = sysA > pA + convB & convA)
    scheduler.addTask(agentA.start, varmap)
    varmap = None
    agentB = agentgraph.createLLMAgent(ovarB, conversation = convB, msg = sysB > convA & convB)
    scheduler.addTask(agentB.start, None)    
    
print("Tasks Enqueued")
print(ovarA.getValue())
print("-----")
print(ovarB.getValue())

scheduler.shutdown() 
