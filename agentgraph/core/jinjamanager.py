from jinja2 import Environment, FileSystemLoader

class JinjaManager:
    def __init__(self, path: str):
        self.path = path

    def runTemplate(self, name: str, data: dict) -> str:
        if data == None:
            data = dict()
        
        file_loader = FileSystemLoader(self.path)
        env = Environment(loader = file_loader)
        template = env.get_template(name)
        output = template.render(data)

        return output
