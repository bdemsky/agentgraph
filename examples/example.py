from agentgraph.exec.Engine import Engine
from agentgraph.graph.LLMModel import LLMModel
from agentgraph.graph.Conversation import Conversation
from agentgraph.graph.Prompts import Prompts
from agentgraph.graph.Var import Var
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

agentA = agentgraph.graph.Graph.createLLMAgent(model, varA, ovarA, msg = sys > (pA + varB) & varA)
agentB = agentgraph.graph.Graph.createLLMAgent(model, varB, ovarB, msg = sys > varA & varB)
eng.shutdown()
