import agentgraph
import agentgraph.config
from dataclasses import dataclass
import os
import random
import time

class Register(agentgraph.core.mutable.Mutable):
    def __init__(self, owner = None):
        super().__init__(owner)
        self.value = 0

    def getValue(self) -> int:
        # inject delays
        time.sleep(random.random())
        self.waitForAccess()
        return self.value

    def setValue(self, num: int):
        """
        a function that sets a register

        Arguments:
        num --- the number to set the register to.
        """
        # inject delays
        time.sleep(random.random())
        self.waitForAccess()
        self.value = num

reg = Register()
cur_dir = os.path.dirname(os.path.abspath(__file__))
prompts = agentgraph.Prompts(cur_dir + "/prompts/")
sys = prompts.loadPrompt("System")
toollist = agentgraph.toolsFromFunctions([reg.setValue])
callVar = agentgraph.Var("Call")
model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000, api_version="2023-12-01-preview")
scheduler = agentgraph.getRootScheduler(model)

for i in range(1, 11, 2):
    pA = prompts.loadPrompt("PromptA", {"num": i})
    ovar = scheduler.runLLMAgent(msg = sys ** pA, callVar=callVar, tools=toollist)
    print("register=", reg.getValue())
    scheduler.runPythonAgent(lambda _, r, n: r.setValue(n), pos=[reg, i+1])
    print("register=", reg.getValue())

scheduler.shutdown()
