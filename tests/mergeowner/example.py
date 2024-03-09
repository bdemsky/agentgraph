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

class RegisterList(agentgraph.core.mutable.Mutable):
    def __init__(self, owner = None):
        super().__init__(owner)
        self.list = []

    def __getitem__(self, index) -> Register:
        self.waitForAccess()
        return self.list[index]

    def append(self, reg: Register):
        self.waitForAccess()
        reg.setOwningObject(self)
        self.list.append(reg)

    def pop(self, *args) -> Register:
        return self.list.pop(*args)

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
reg = Register()
reglist = RegisterList()

def testFunc1(scheduler, reg, reglist) -> list:
    reglist.append(reg)
    scheduler.runPythonAgent(lambda _, rl, n: rl[0].setValue(n), pos=[reglist, 1])
    print(reg.getValue())
    scheduler.runPythonAgent(lambda _, r, n: r.setValue(n), pos=[reg, 2])
    print(reg.getValue())

    return []

# nested scope
scheduler.runPythonAgent(testFunc1, pos=[reg, reglist])
scheduler.runPythonAgent(lambda _, rl, n: rl[0].setValue(n), pos=[reglist, 3])
print(reg.getValue())
scheduler.runPythonAgent(lambda _, r, n: r.setValue(n), pos=[reg, 4])
print(reg.getValue())

# loop
for i in range(1, 5, 2):
    scheduler.runPythonAgent(lambda _, rl, n: rl[0].setValue(n), pos=[reglist, i])
    print(reg.getValue())
    scheduler.runPythonAgent(lambda _, r, n: r.setValue(n), pos=[reg, i+1])
    print(reg.getValue())
    # add a new register to toollist every iteration
    reglist.pop()
    reg = Register()
    reglist.append(reg)

scheduler.shutdown()
