from jinja2 import Environment, FileSystemLoader

class Prompts:
    def __init__(self, path: str):
        self.path = path

    def createPrompt(self, prompt_name: str, data: dict) -> str:
        if data == None:
            data = dict()
        
        file_loader = FileSystemLoader(self.path)
        env = Environment(loader = file_loader)
        env.get_template(prompt_name)
        output = template.render(data)

        return output
