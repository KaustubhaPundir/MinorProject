from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Flowable, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
pdfmetrics.registerFontFamily('Arial', normal='Arial', bold='Arial-Bold', italic='Arial', boldItalic='Arial-Bold')
styles = getSampleStyleSheet()
for key in ('Normal','BodyText','Heading1','Heading2','Heading3','Title'):
    styles[key].fontName = 'Arial-Bold' if key.startswith('Heading') or key=='Title' else 'Arial'
styles['BodyText'].fontSize=9
styles['BodyText'].leading=13
styles['BodyText'].spaceAfter=6
styles['Heading1'].fontSize=17; styles['Heading1'].leading=21
styles['Heading2'].fontSize=12; styles['Heading2'].leading=16
styles['Heading3'].fontSize=10; styles['Heading3'].leading=14
styles.add(ParagraphStyle(name='Cell',fontName='Arial',fontSize=7.8,leading=11,spaceAfter=0,wordWrap='CJK'))
styles.add(ParagraphStyle(name='Small',parent=styles['BodyText'],fontSize=8,textColor=colors.HexColor('#53657b')))

def clean(s):
    # Older Windows-edited notes contain UTF-8 text interpreted as cp1252.
    for _ in range(2):
        if not any(c in s for c in ('\u00e2','\u00c3')): break
        try: s=s.encode('cp1252').decode('utf-8')
        except (UnicodeError,LookupError): break
    return s.replace('\u2014',' - ').replace('\u2013','-').replace('\u2011','-').replace('\u2192',' -> ').replace('\ufffd','-')

def markup(s):
    s=escape(clean(s))
    s=re.sub(r'`([^`]+)`',r'<font color="#185375">\1</font>',s)
    s=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',s)
    return s

class Architecture(Flowable):
    def __init__(self): super().__init__(); self.width=475; self.height=250
    def draw(self):
        c=self.canv
        steps=['Browser upload + Convert','Local backend: validate, infer domain and route','Stable COBOL reference suite in Docker','Groq: direct Python or validated IR + emitter','Candidate Docker run + exact comparison','Bounded AI repair OR independent acceptance','Integrity verification + accepted Python / reports']
        for i,label in enumerate(steps):
            y=220-i*34
            c.setFillColor(colors.HexColor('#edf3fa')); c.setStrokeColor(colors.HexColor('#a8bfd4'))
            c.roundRect(12,y,450,25,5,fill=1,stroke=1)
            c.setFillColor(colors.HexColor('#18374f'));c.setFont('Arial',9);c.drawCentredString(237,y+9,label)
            if i<6:
                c.line(237,y,237,y-9)
                c.line(237,y-9,234,y-6);c.line(237,y-9,240,y-6)

story=[]
story += [Paragraph('LEGACY DIFF',styles['Title']),Paragraph('Project summary, architecture and conversion scope',styles['Heading2']),Paragraph('18 November 2026 | COBOL-to-Python differential validation',styles['Small']),Spacer(1,12)]
text=(ROOT/'docs/project-progress-summary.md').read_text(encoding='utf-8')
lines=text.splitlines(); i=0
while i<len(lines):
    line=lines[i].strip()
    if not line or line.startswith('# Legacy Diff'): i+=1;continue
    if line.startswith('```'):
        kind=line[3:];i+=1; block=[]
        while i<len(lines) and not lines[i].startswith('```'): block.append(lines[i]);i+=1
        i+=1
        if kind=='mermaid':
            story.append(PageBreak())
            story.append(Paragraph('Updated architecture flowchart',styles['Heading1']))
            story.append(Image(str(ROOT/'output/pdf/architecture-flowchart.png'),width=475,height=600))
            story.append(Spacer(1,8))
            story.append(Paragraph('User-supplied architecture diagram. In the current upload-only interface, the input domain is inferred automatically; explicit manual review remains available through CLI manifests. No-input acceptance independently repeats the singleton case.',styles['Small']))
            story.append(PageBreak())
        else:
            for row in block: story.append(Paragraph(markup(row),styles['Small']))
        continue
    if line.startswith('|'):
        rows=[]
        while i<len(lines) and lines[i].strip().startswith('|'):
            row=[x.strip() for x in lines[i].strip().strip('|').split('|')]
            if not all(re.fullmatch(r'[:\- ]+',x) for x in row): rows.append(row)
            i+=1
        n=len(rows[0]); widths=([145,330] if n==2 else [100,120,255] if n==3 else [85,105,145,140])
        data=[[Paragraph(('<b>'+markup(x)+'</b>') if r==0 else markup(x),styles['Cell']) for x in row] for r,row in enumerate(rows)]
        t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dfeaf4')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#c3cfdb')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f8fb')])]))
        story.extend([t,Spacer(1,10)]);continue
    if line.startswith('#'):
        level=len(line)-len(line.lstrip('#'));story.append(Paragraph(markup(line.lstrip('#').strip()),styles['Heading1' if level==2 else 'Heading2']));i+=1;continue
    if line.startswith('- ') or re.match(r'^\d+\. ',line):
        story.append(Paragraph(markup(line),styles['BodyText']));i+=1;continue
    paragraph=[line];i+=1
    while i<len(lines) and lines[i].strip() and not lines[i].strip().startswith(('#','|','```','- ')) and not re.match(r'^\d+\. ',lines[i].strip()): paragraph.append(lines[i].strip());i+=1
    story.append(Paragraph(markup(' '.join(paragraph)),styles['BodyText']))

def footer(c,doc):
    c.setStrokeColor(colors.HexColor('#cbd6e2'));c.line(48,40,547,40)
    c.setFont('Arial',8);c.setFillColor(colors.HexColor('#53657b'));c.drawString(48,27,'Legacy Diff | Project summary');c.drawRightString(547,27,str(doc.page))

out=ROOT/'output/pdf/legacy-diff-project-summary.pdf'
SimpleDocTemplate(str(out),pagesize=(595.28,841.89),leftMargin=60,rightMargin=60,topMargin=48,bottomMargin=56,title='Legacy Diff - Project Summary',author='Legacy Diff Project').build(story,onFirstPage=footer,onLaterPages=footer)
print(out)
