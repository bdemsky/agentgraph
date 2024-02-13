from agentgraph.core.conversation import Conversation
from agentgraph.core.jinjamanager import JinjaManager
from agentgraph.core.msgseq import MsgSeq

class Prompt(MsgSeq):
    def __init__(self, prompts: 'Prompts', name: str, vars: set):
        super().__init__()
        self.prompts = prompts
        self.name = name
        self.vars = vars

    def isSingleMsg(self) -> bool:
        return True

    def exec(self, varsMap: dict) -> str:
        """Compute value of prompt at runtime"""
        data = dict()
        for var in varsMap:
            value = varsMap[var]
            data[var.getName()] = value
        val = self.prompts.runTemplate(self.name, data)
        return val

    def getVars(self) -> set:
        return self.vars

class Prompts(JinjaManager):
    def loadPrompt(self, prompt_name: str, vars: set = None) -> Prompt:
        if vars == None:
            vars = set()
        return Prompt(self, prompt_name, vars)
