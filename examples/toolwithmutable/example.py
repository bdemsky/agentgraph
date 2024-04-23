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

    def get_value(self) -> int:
        # inject delays
        time.sleep(random.random())
        self.wait_for_access()
        return self.value

    def setValue(self, num: int):
        """
        a function that sets a register

        Arguments:
        num --- the number to set the register to.
        """
        # inject delays
        time.sleep(random.random())
        self.wait_for_access()
        self.value = num

reg = Register()
cur_dir = os.path.dirname(os.path.abspath(__file__))
prompts = agentgraph.Prompts(cur_dir + "/prompts/")
sys = prompts.load_prompt("System")
toollist = agentgraph.tools_from_functions([reg.setValue])
callVar = agentgraph.Var("Call")
model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000, api_version="2023-12-01-preview")
scheduler = agentgraph.get_root_scheduler(model)

for i in range(1, 11, 2):
    pA = prompts.load_prompt("PromptA", {"num": i})
    ovar = scheduler.run_llm_agent(msg = sys ** pA, callVar=callVar, tools=toollist)
    print("register=", reg.get_value())
    scheduler.run_python_agent(lambda _, r, n: r.setValue(n), pos=[reg, i+1])
    print("register=", reg.get_value())

scheduler.shutdown()
