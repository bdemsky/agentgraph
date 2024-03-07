import agentgraph
from dataclasses import dataclass
import os

from register import Register

cur_dir = os.path.dirname(os.path.abspath(__file__))
prompts = agentgraph.Prompts(cur_dir + "/prompts/")
sys = prompts.loadPrompt("System")
callVar = agentgraph.Var("Call")


model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000, api_version="2023-12-01-preview")
scheduler = agentgraph.getRootScheduler(model)

reg = Register()
toollist = agentgraph.toolsFromFunctions([reg.setValue])

for i in range(0, 10, 2):
    pA = prompts.loadPrompt("PromptA", {"num": i})
    ovar = scheduler.runLLMAgent(msg = sys ** pA, callVar=callVar, tools=toollist)
    assert reg.getValue() == i
    print("call: ", callVar.getValue(), "out: ", ovar.getValue())
    scheduler.runPythonAgent(lambda _, r, n: r.setValue(n), pos=[reg, i+1])
    assert reg.getValue() == i + 1
    # add a new register to toollist every iteration
    toollist.pop()
    reg = Register()
    toollist.append(agentgraph.ToolReflect(reg.setValue))

scheduler.shutdown()
