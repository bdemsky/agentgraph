import agentgraph
import os
import time


def testFunc1(scheduler, fs) -> list:
    print("testFunc1 start")
    scheduler.run_python_agent(testFunc2, pos=[fs])
    print("testFunc1 end")
    return []

def testFunc2(scheduler, fs) -> list:
    time.sleep(3)
    fs["a"]="1"
    return []


model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.get_root_scheduler(model)
fs = agentgraph.FileStore()
fs["a"]="0"
scheduler.run_python_agent(testFunc1, pos=[fs])

print("Dispatched all")
print(1,fs["a"])

scheduler.shutdown()
