from agentgraph.core.conversation import Conversation
from agentgraph.core.jinjamanager import JinjaManager
from agentgraph.core.mutable import Mutable
from agentgraph.core.msgseq import MsgSeq
from agentgraph.core.var import Var

class Prompt(MsgSeq):
    def __init__(self, prompts: 'Prompts', name: str, vals: dict):
        super().__init__()
        self.prompts = prompts
        self.name = name
        self.vals = vals

    def isSingleMsg(self) -> bool:
        return True

    def exec(self, varsMap: dict) -> str:
        """Compute value of prompt at runtime"""
        data = dict()
        # Take input map and resolve and variables that were used
        for name in self.vals:
            val = self.vals[name]
            if isinstance(val, Var):
                data[name] = varsMap[val]
            else:
                data[name] = val
        val = self.prompts.runTemplate(self.name, data)
        return val

    def getReadSet(self) -> set:
        readset = set()
        for name in self.vals:
            val = self.vals[name]
            if isinstance(val, Var):
                readset.add(val)
            elif isinstance(val, Mutable):
                readset.add(val)
        return readset

class Prompts(JinjaManager):
    def loadPrompt(self, prompt_name: str, vals: dict = None) -> Prompt:
        if vals == None:
            vals = dict()
        return Prompt(self, prompt_name, vals)
