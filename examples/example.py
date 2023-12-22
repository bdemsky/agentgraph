from agentgraph.exec.Engine import Engine
from agentgraph.graph.LLMModel import LLMModel
import agentgraph.graph.Graph
import os

def testFunc(inVars: dict) -> dict:
    print("Test")
    return dict()

eng = Engine()
model = LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
agentpair = agentgraph.graph.Graph.createPythonAgent(testFunc)
graph = agentgraph.graph.Graph.createRunnable(agentpair)
eng.runGraph(graph, dict())

eng.shutdown()
