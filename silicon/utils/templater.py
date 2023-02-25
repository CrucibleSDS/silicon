from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from pdflatex import pdflatex


class Templater:
    def __init__(self):
        self.file_loader = FileSystemLoader(Path(__file__).parent)
        self.env = Environment(loader=self.file_loader)
        self.template = self.env.get_template('template.tex')

    def template_tex(self, data: dict[str, any]) -> str:
        return self.template.render(data=data)

    def generate_pdf(self, data: dict[str, any]) -> BytesIO:
        pdfl = pdflatex.PDFLaTeX.from_jinja_template(self.template, data=data)
        pdf, log, cp = pdfl.create_pdf()
        return BytesIO(pdf)
