import agentgraph
from dataclasses import dataclass
import os

from register import Register

reg = Register()
cur_dir = os.path.dirname(os.path.abspath(__file__))
toollist = agentgraph.core.tools.ToolList()
prompts = agentgraph.Prompts(cur_dir + "/prompts/")
sys = prompts.loadPrompt("System")
callVar = agentgraph.Var("Call")

def testFunc1(scheduler, reg, toollist) -> list:
    toollist.append(agentgraph.ToolReflect(reg.setValue))
    pA = prompts.loadPrompt("PromptA", {"num": 1})
    ovar = scheduler.runLLMAgent(msg = sys ** pA, callVar=callVar, tools=toollist)
    print("register=", reg.getValue())
    scheduler.runPythonAgent(lambda _, r, n: r.setValue(n), pos=[reg, 2])
    print("call: ", callVar.getValue(), "out: ", ovar.getValue())
    print("register=", reg.getValue())

    return []

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000, api_version="2023-12-01-preview")
scheduler = agentgraph.getRootScheduler(model)

scheduler.runPythonAgent(testFunc1, pos=[reg, toollist])
pA = prompts.loadPrompt("PromptA", {"num": 3})
ovar = scheduler.runLLMAgent(msg = sys ** pA, callVar=callVar, tools=toollist)
print("register=",reg.getValue())
scheduler.runPythonAgent(lambda _, r, n: r.setValue(n), pos=[reg, 4])
print("call: ", callVar.getValue(), "out: ", ovar.getValue())
print("register=", reg.getValue())

scheduler.shutdown()
