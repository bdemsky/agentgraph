import agentgraph
import os
import time


def testFunc1(scheduler, fs) -> list:
    fs["a"] = fs["a"] + "1"
    return [3]

def testFunc2(scheduler, fs) -> list:
    fs["a"] = fs["a"] + "2"
    return [4]

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.get_root_scheduler(model)
fs = agentgraph.FileStore()
fs["a"]="0"
vara = scheduler.run_python_agent(testFunc1, pos=[fs], numOuts = 1)
varb = scheduler.run_python_agent(testFunc2, pos=[fs], numOuts = 1)

print(fs["a"])
print(vara.get_value())
print(varb.get_value())

scheduler.shutdown()
