from agentgraph.exec.Engine import Engine
from agentgraph.graph.LLMModel import LLMModel
import os

eng = Engine()
model = LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
eng.shutdown()
