import agentgraph
import os
import time


model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.get_root_scheduler(model)
prompts = agentgraph.Prompts("./examples/cookie/prompts/")

sys = prompts.load_prompt("System")
pA = prompts.load_prompt("PromptA")
ovarA = scheduler.run_llm_agent(msg = sys ** pA)
ovarR = ovarA

for i in range(3):
    pB = prompts.load_prompt("PromptB", { 'Recipe': ovarR})
    ovarB = scheduler.run_llm_agent(msg = sys ** pB)
    ovarR = ovarB
    
print("Tasks Enqueued")
print(ovarA.get_value())
print("-----")
print(ovarB.get_value())

scheduler.shutdown() 
