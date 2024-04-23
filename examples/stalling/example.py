import agentgraph
import os
import time
from agentgraph.exec.engine import Engine


def testFuncA1(scheduler, i, start) -> list:
    time.sleep(0.5)
    print("TestA1", i, time.time() - start)
    out_var = scheduler.run_python_agent(testFuncA2, pos=[i + 1, start], numOuts=1)
    out_var = scheduler.run_python_agent(testFuncA3, pos=[out_var, start], numOuts=1)
    
    out_val = out_var.get_value()
    print("TestA4", out_val, time.time() - start)
    return []

def testFuncA2(scheduler, i, start) -> list:
    time.sleep(0.5)
    print("TestA2", i, time.time() - start)
    return [i + 1]

def testFuncA3(scheduler, i, start) -> list:
    time.sleep(0.5)
    print("TestA3", i, time.time() - start)
    return [i + 1]


def testFuncB1(scheduler, i, start) -> list:
    time.sleep(0.5)
    print("TestB1", i, time.time() - start)
    out_var = scheduler.run_python_agent(testFuncB2, pos=[i + 1, start], numOuts=1)
    out_var2 = scheduler.run_python_agent(testFuncB3, pos=[i + 2, start], numOuts=1)
    
    out_val = out_var.get_value()
    out_val2 = out_var2.get_value()
    print("TestB4", out_val, out_val2, time.time() - start)
    return []

def testFuncB2(scheduler, i, start) -> list:
    time.sleep(0.5)
    print("TestB2", i, time.time() - start)
    return [i + 1]

def testFuncB3(scheduler, i, start) -> list:
    time.sleep(1)
    print("TestB3", i, time.time() - start)
    return [i + 1]

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
NUM_THREADS = 1
scheduler = agentgraph.get_root_scheduler(model, Engine(concurrency=NUM_THREADS))
start = time.time()
out_var = None
for i in range(NUM_THREADS):
    scheduler.run_python_agent(testFuncA1, pos=[i * 10 + 10, start])
    scheduler.run_python_agent(testFuncB1, pos=[i * 10 + 10, start])
scheduler.shutdown()