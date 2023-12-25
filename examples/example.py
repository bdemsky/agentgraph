from agentgraph.exec.Engine import Engine
from agentgraph.graph.LLMModel import LLMModel
from agentgraph.graph.Conversation import Conversation
from agentgraph.graph.Prompts import Prompts
from agentgraph.graph.Var import Var
from agentgraph.graph.BoolVar import BoolVar
import agentgraph.graph.Graph
import os
import time

eng = Engine()
model = LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
convA = Conversation()
convB = Conversation()
varA = Var("A")
varB = Var("B")
ovarA = Var("OA")
ovarB = Var("OB")
d = {varA: convA, varB: convB}
prompts = Prompts("./examples/prompts/")
sys = prompts.createPrompt("System")
pA = prompts.createPrompt("PromptA")
varLoop = BoolVar("loop")
d = dict()
d[varLoop] = True
d[varA] = convA
d[varB] = convB

agentA = agentgraph.graph.Graph.createLLMAgent(model, varA, ovarA, msg = sys > (pA + varB) & varA)
agentB = agentgraph.graph.Graph.createLLMAgent(model, varB, ovarB, msg = sys > varA & varB)
loop = agentgraph.graph.Graph.createDoWhile(agentA | agentB, varLoop)
eng.runGraph(loop, d)
eng.shutdown()
