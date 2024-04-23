import agentgraph
import os
import time


def testFunc1(scheduler) -> list:
    prompts = agentgraph.Prompts("./examples/pythonchild/prompts/")
    sys = prompts.load_prompt("System")
    pA = prompts.load_prompt("PromptA")
    ovarA = scheduler.run_llm_agent(msg = sys ** pA)
    ovarR = ovarA
    
    for i in range(3):
        pB = prompts.load_prompt("PromptB", {'Recipe': ovarR})
        ovarB = scheduler.run_llm_agent(msg = sys ** pB)
        ovarR = ovarB

    print("Tasks Enqueued")
    print(ovarA.get_value())
    return []

def testFunc2(scheduler, bar: int) -> list:
    print("TestB", bar)
    return []

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.get_root_scheduler(model)
scheduler.run_python_agent(testFunc1)
scheduler.run_python_agent(testFunc2, pos=[3])
scheduler.shutdown()
