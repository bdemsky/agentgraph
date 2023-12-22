from agentgraph.exec.Engine import Engine
from agentgraph.graph.LLMModel import LLMModel
import agentgraph.graph.Graph
import os
import time

async def testFunc(inVars: dict) -> dict:
    print("Test")
    return None

eng = Engine()
model = LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
agentpair = agentgraph.graph.Graph.createPythonAgent(testFunc)
graph = agentgraph.graph.Graph.createRunnable(agentpair)
eng.runGraph(graph, dict())
time.sleep(2)
eng.shutdown()
