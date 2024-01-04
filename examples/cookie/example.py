from agentgraph.core.llmmodel import LLMModel
from agentgraph.core.conversation import Conversation
from agentgraph.core.prompts import Prompts
from agentgraph.core.var import Var
from agentgraph.core.mutvar import MutVar
from agentgraph.core.boolvar import BoolVar
from agentgraph import VarMap
import agentgraph
import os
import time


scheduler = agentgraph.getRootScheduler()
model = LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
prompts = Prompts("./examples/cookie/prompts/")

sys = prompts.createPrompt("System")
g = VarMap()
varA = g.mapToConversation("A")
ovarA = Var("Recipe")
pA = prompts.createPrompt("PromptA")
agentA = agentgraph.createLLMAgent(model, varA, ovarA, msg = sys > pA)
scheduler.addTask(agentA.start, g)
ovarR = ovarA

for i in range(2):
    pB = prompts.createPrompt("PromptB", {ovarR})
    gnew = VarMap()
    varB = gnew.mapToConversation("B")
    ovarB = Var("Recipe")
    agentB = agentgraph.createLLMAgent(model, varB, ovarB, msg = sys > pB)
    scheduler.addTask(agentB.start, gnew)
    ovarR = ovarB
    
print("Tasks Enqueued")
print(scheduler.readVariable(ovarA))
print("-----")
print(scheduler.readVariable(ovarB))

scheduler.shutdown() 
