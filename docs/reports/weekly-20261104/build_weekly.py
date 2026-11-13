"""Build a searchable weekly report from the reviewed Markdown source."""
from pathlib import Path
import html
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).with_name('WEEK-01.md')
OUT = ROOT / 'output/pdf/Team_Wifi_1주차_수행일지_20261104.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold', 'C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Malgun', normal='Malgun', bold='MalgunBold')
INK = colors.HexColor('#202830')
ACCENT = colors.HexColor('#234A5D')
WIDTH = A4[0] - 84
STYLES = {
    'title': ParagraphStyle('Title', fontName='MalgunBold', fontSize=23, leading=32, textColor=colors.black, spaceAfter=14),
    'h2': ParagraphStyle('Heading', fontName='MalgunBold', fontSize=15, leading=22, textColor=INK, spaceBefore=14, spaceAfter=8, keepWithNext=True),
    'h3': ParagraphStyle('Subheading', fontName='MalgunBold', fontSize=11.2, leading=17, textColor=ACCENT, spaceBefore=10, spaceAfter=5, keepWithNext=True),
    'body': ParagraphStyle('Body', fontName='Malgun', fontSize=10, leading=15.5, textColor=INK, wordWrap='CJK', spaceAfter=8),
    'cell': ParagraphStyle('Cell', fontName='Malgun', fontSize=9.1, leading=13.5, textColor=INK, wordWrap='CJK'),
    'head': ParagraphStyle('TableHeading', fontName='MalgunBold', fontSize=9.1, leading=13.5, textColor=colors.white, wordWrap='CJK'),
    'caption': ParagraphStyle('Caption', fontName='Malgun', fontSize=8.4, leading=12.5, textColor=colors.HexColor('#52616A'), wordWrap='CJK', spaceAfter=6),
}


def inline(text):
    text = html.escape(text)
    text = text.replace('&lt;br/&gt;', '<br/>')
    text = re.sub(r'\[([^\]]+)\]\((https://[^)]+)\)', r'<link href="\2" color="#234A5D"><u>\1</u></link>', text)
    return re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)


def para(text, kind='body'):
    return Paragraph(inline(text), STYLES[kind])


def table(lines):
    data = [[cell.strip() for cell in line.strip().strip('|').split('|')] for line in lines]
    data = [row for row in data if not all(re.fullmatch(r'[-: ]+', c) for c in row)]
    n = len(data[0])
    if n == 2:
        widths = [112, WIDTH - 112]
    elif data[0][0] == '기록 시점':
        widths = [82, 207, WIDTH - 289]
    elif data[0][0] == '제공 자료':
        widths = [99, 162, WIDTH - 261]
    elif data[0][0] == '모델':
        widths = [WIDTH - 220, 110, 110]
    elif data[0][0] == '작업':
        widths = [140, 138, WIDTH - 278]
    else:
        widths = [135, 132, WIDTH - 267]
    rendered = [[para(c, 'head' if idx == 0 else 'cell') for c in row] for idx, row in enumerate(data)]
    t = Table(rendered, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F4F6')]),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#D9D9D9')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return [t, Spacer(1, 9)]


class ReportCanvas(Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.states = []

    def showPage(self):
        self.states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        pages = len(self.states)
        for state in self.states:
            self.__dict__.update(state)
            self.setFont('Malgun', 8)
            self.setFillColor(colors.HexColor('#65717A'))
            self.drawString(42, 25, 'Team_Wifi  |  1주차 수행일지  |  2026.11.04')
            self.drawRightString(A4[0] - 42, 25, f'{self._pageNumber} / {pages}')
            super().showPage()
        super().save()


story = []
lines = SOURCE.read_text(encoding='utf-8').splitlines()
i = 0
while i < len(lines):
    line = lines[i].strip()
    if not line:
        i += 1
        continue
    if line == '<!-- pagebreak -->':
        story.append(PageBreak())
    elif line == '<!-- screenshots -->':
        image_width = 222
        images = [Image(str(SOURCE.parent / 'assets' / name), width=image_width,
                        height=image_width * 841 / 555) for name in ('live-advisor-result.jpg', 'live-guide.jpg')]
        t = Table([images], colWidths=[WIDTH / 2, WIDTH / 2])
        t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                              ('BOX', (0, 0), (0, 0), 0.4, colors.HexColor('#D9D9D9')),
                              ('BOX', (1, 0), (1, 0), 0.4, colors.HexColor('#D9D9D9'))]))
        story.extend([t, Spacer(1, 10)])
    elif line.startswith('|'):
        rows = []
        while i < len(lines) and lines[i].strip().startswith('|'):
            rows.append(lines[i]); i += 1
        story.extend(table(rows))
        continue
    elif line.startswith('### '):
        story.append(para(line[4:], 'h3'))
    elif line.startswith('## '):
        story.append(para(line[3:], 'h2'))
    elif line.startswith('# '):
        story.append(para(line[2:], 'title'))
    elif line.startswith('- '):
        story.append(para('• ' + line[2:]))
    else:
        story.append(para(line))
    i += 1

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=42, rightMargin=42, topMargin=35, bottomMargin=43,
                        title='모두의 육아 1주차 수행일지', author='Team_Wifi', subject='핀테크 데이터 분석 프로젝트 수행일지')
doc.build(story, canvasmaker=ReportCanvas)
print(OUT)
