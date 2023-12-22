from agentgraph.exec.Engine import Engine
from agentgraph.graph.LLMModel import LLMModel
import agentgraph.graph.Graph
import os
import time

async def testFunc(inVars: dict) -> dict:
    print("TestA")
    return None

async def testFunc2(inVars: dict) -> dict:
    print("TestB")
    return None

eng = Engine()
model = LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
agentpair = agentgraph.graph.Graph.createPythonAgent(testFunc) | \
    agentgraph.graph.Graph.createPythonAgent(testFunc2) | \
    agentgraph.graph.Graph.createPythonAgent(testFunc2)
graph = agentgraph.graph.Graph.createRunnable(agentpair)
eng.runGraph(graph, dict())
eng.runGraph(graph, dict())
eng.shutdown()
