import os
import re
import subprocess
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from jinja2 import Environment, FileSystemLoader
from PyPDF2 import PdfMerger


class Templater:
    def __init__(self):
        self.file_loader = FileSystemLoader(Path(__file__).parent)
        self.env = Environment(loader=self.file_loader)
        self.template = self.env.get_template('template.tex')

    def generate_pdf(self, data: dict[str, any]) -> BytesIO:
        data['graphicspath'] = f"{(Path(__file__).parent / 'img').absolute()}{os.sep}"

        with TemporaryDirectory() as td:
            args = [
                'pdflatex',
                '-interaction-mode=batchmode',
                f'-output-directory={td}',
                '-jobname=template',
                '-shell-escape',
            ]
            subprocess.run(args,
                           input=self.template.render(data=data).encode(encoding='utf-8'),
                           cwd=td,
                           timeout=15,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
            with open(Path(td, 'template.pdf'), 'rb') as f:
                pdf = f.read()
        return BytesIO(pdf)


def merge_pdf(pdfs: list[BytesIO]) -> BytesIO:
    bytesio = BytesIO()
    merger = PdfMerger()
    for pdf in pdfs:
        merger.append(pdf)
    merger.write(bytesio)
    merger.close()
    return bytesio


def tex_escape(text):
    """
        :param text: a plain text message
        :return: the message escaped to appear correctly in LaTeX
    """
    conv = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
        '<': r'\textless{}',
        '>': r'\textgreater{}',
    }
    regex = re.compile('|'.join(re.escape(str(key))
                                for key in sorted(conv.keys(), key=lambda item: - len(item))))
    return regex.sub(lambda match: conv[match.group()], text)


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
