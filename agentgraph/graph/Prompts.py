from jinja2 import Environment, FileSystemLoader
from agentgraph.graph.MsgSeq import MsgSeq

class Prompt(MsgSeq):
    def __init__(self, prompts: 'Prompts', name: str, vars: set):
        super().__init__()
        self.prompts = prompts
        self.name = name
        self.vars = vars

    def isSingleMsg(self) -> bool:
        return True

    def exec(self, varsMap: dict):
        """Compute value of prompt at runtime"""
        data = dict()
        for var, value in varsMap:
            data[var.getName()] = value

        val = self.prompts.runPrompt(self.name, data)
        return Conversation(val)

    def getVars(self) -> set:
        return self.vars
    
class Prompts:
    def __init__(self, path: str):
        self.path = path

    def createPrompt(self, prompt_name: str, vars: set = None) -> Prompt:
        if vars == None:
            vars = {}
        return Prompt(self, prompt_name, set)

    def runPrompt(self, prompt_name: str, data: dict) -> str:
        if data == None:
            data = dict()
        
        file_loader = FileSystemLoader(self.path)
        env = Environment(loader = file_loader)
        env.get_template(prompt_name)
        output = template.render(data)

        return output
