from jinja2 import Environment, FileSystemLoader
from agentgraph.graph.MsgSeq import MsgSeq

class Prompt(MsgSeq):
    def __init__(self, prompts: 'Prompts', name: str, vars: set):
        super().__init__()
        self.prompts = prompts
        self.name = name
        self.vars = vars
        
class Prompts:
    def __init__(self, path: str):
        self.path = path

    def createPrompt(self, prompt_name: str, vars: set) -> str:
        if data == None:
            data = dict()
        
        file_loader = FileSystemLoader(self.path)
        env = Environment(loader = file_loader)
        env.get_template(prompt_name)
        output = template.render(data)

        return output
