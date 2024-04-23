import agentgraph
import os
import time


def testFunc1(scheduler, fs) -> list:
    print("testFunc1 start")
    time.sleep(2)
    print(0, fs["a"])
    fs["a"]="1"
    print("testFunc1 end")
    return [fs]

def testFunc2(scheduler, fs) -> list:
    print(1, fs["a"])
    fs["a"]="2"
    return [fs]

def testFunc3(scheduler, fs) -> list:
    print(2, fs["a"])
    fs["a"]="3"
    return []

def testFunc4(scheduler, fs) -> list:
    print(3, fs["a"])
    fs["a"]="4"
    return []

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.get_root_scheduler(model)
fs = agentgraph.FileStore()
fs["a"]="0"
out=scheduler.run_python_agent(testFunc1, numOuts=1, pos=[fs])
out2=scheduler.run_python_agent(testFunc2, numOuts=1, pos=[out])
scheduler.run_python_agent(testFunc3, pos=[out2])
scheduler.run_python_agent(testFunc4, pos=[fs])

print("Dispatched all")
print(4,fs["a"])

scheduler.shutdown()
