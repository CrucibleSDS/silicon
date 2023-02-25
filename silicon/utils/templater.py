from pathlib import Path

from jinja2 import Environment, FileSystemLoader


class Templater:
    def __init__(self):
        self.file_loader = FileSystemLoader(Path(__file__).parent)
        self.env = Environment(loader=self.file_loader)
        self.template = self.env.get_template('template.tex')

    def template_front_page(self, data: dict[str, any]) -> str:
        return self.template.render(data=data)
