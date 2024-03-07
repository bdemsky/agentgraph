import agentgraph
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
