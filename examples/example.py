from agentgraph.exec.Engine import Engine
from agentgraph.core.LLMModel import LLMModel
from agentgraph.core.Conversation import Conversation
from agentgraph.core.Prompts import Prompts
from agentgraph.core.Var import Var
from agentgraph.core.MutVar import MutVar
from agentgraph.core.BoolVar import BoolVar
import agentgraph.graph
import os
import time

eng = Engine()
model = LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
convA = Conversation()
convB = Conversation()
varA = MutVar("A")
varB = MutVar("B")
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

agentA = agentgraph.graph.createLLMAgent(model, varA, ovarA, msg = sys > (pA + varB) & varA)
agentB = agentgraph.graph.createLLMAgent(model, varB, ovarB, msg = sys > varA & varB)
loop = agentgraph.graph.createDoWhile(agentA | agentB, varLoop)
eng.runGraph(loop, d)
eng.shutdown()
