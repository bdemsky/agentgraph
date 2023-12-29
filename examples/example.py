from agentgraph.exec.Engine import Engine
from agentgraph.core.LLMModel import LLMModel
from agentgraph.core.Conversation import Conversation
from agentgraph.core.Prompts import Prompts
from agentgraph.core.Var import Var
from agentgraph.core.MutVar import MutVar
from agentgraph.core.BoolVar import BoolVar
from agentgraph import graph
import agentgraph
import os
import time

eng = Engine()
g = graph()
model = LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
varA = g.createConversation("A")
varB = g.createConversation("B")
varLoop = g.createBoolVar("loop", True)
ovarA = Var("OA")
ovarB = Var("OB")
prompts = Prompts("./examples/prompts/")
sys = prompts.createPrompt("System")
pA = prompts.createPrompt("PromptA")

agentA = agentgraph.createLLMAgent(model, varA, ovarA, msg = sys > (pA + varB) & varA)
agentB = agentgraph.createLLMAgent(model, varB, ovarB, msg = sys > varA & varB)
loop = agentgraph.createDoWhile(agentA | agentB, varLoop)
eng.runGraph(loop, g)
eng.shutdown() 
