from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from pdflatex import pdflatex
from PyPDF2 import PdfFileMerger


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


def merge_pdf(pdfs: list[BytesIO]) -> BytesIO:
    merger = PdfFileMerger()
    for pdf in pdfs:
        merger.append(pdf)
    bytesio = BytesIO()
    merger.write(bytesio)
    return bytesio


def fix_si(amount):
    prefixes = [
        ('T', 1e12),
        ('G', 1e9),
        ('M', 1e6),
        ('k', 1e3),
        ('', 1),
        ('m', 1e-3),
        ('µ', 1e-6),
        ('n', 1e-9)]
    for prefix, factor in prefixes:
        if amount >= factor:
            return f'{amount / factor:.2f}{prefix}g'
    return f'{amount}g'
