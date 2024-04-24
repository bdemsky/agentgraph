import agentgraph
import os
import time


model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.get_root_scheduler(model)
prompts = agentgraph.Prompts("./examples/chat/prompts/")

sysA = prompts.load_prompt("SystemA")
sysB = prompts.load_prompt("SystemB")
pA = prompts.load_prompt("PromptA")
convA = agentgraph.Conversation()
convB = agentgraph.Conversation()
varmap = agentgraph.VarMap()
ovarB = varmap.map_to_none()

for i in range(2):
    ovarA = scheduler.run_llm_agent(conversation = convA, msg = convA > (convA & ovarB | sysA ** pA), vmap = varmap)
    varmap = None
    ovarB = scheduler.run_llm_agent(conversation = convB, msg = convB > (convB & ovarA | sysB ** ovarA))
    
print("Tasks Enqueued")
print(ovarA.get_value())
print("-----")
print(ovarB.get_value())

scheduler.shutdown() 
