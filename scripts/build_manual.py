"""Rebuild the branded handover PDF. Requires ReportLab (app requirements)."""
from pathlib import Path
import csv
import re
from html import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether, Image
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parent.parent
DEST=ROOT/'docs/Bancapp_Deployment_Features_and_SOP_Manual.pdf'
NAVY=colors.HexColor('#142e65'); BLUE=colors.HexColor('#3468df'); VIOLET=colors.HexColor('#6855bc')
INK=colors.HexColor('#23324b'); MUTED=colors.HexColor('#59677a'); PALE=colors.HexColor('#f1f5fc'); LINE=colors.HexColor('#d9e2f0')
WIDTH,HEIGHT=A4; LEFT=44; RIGHT=44; TOP=76; BOTTOM=48; CW=WIDTH-LEFT-RIGHT
FONTDIR=Path('/usr/share/fonts/truetype/dejavu')
if FONTDIR.exists():
    for name,file in [('Bancapp','DejaVuSans.ttf'),('Bancapp-Bold','DejaVuSans-Bold.ttf'),('Bancapp-Italic','DejaVuSans-Oblique.ttf'),('Bancapp-Mono','DejaVuSansMono.ttf')]:
        pdfmetrics.registerFont(TTFont(name,str(FONTDIR/file)))
    pdfmetrics.registerFontFamily('Bancapp',normal='Bancapp',bold='Bancapp-Bold',italic='Bancapp-Italic',boldItalic='Bancapp-Bold')
    F='Bancapp';FB='Bancapp-Bold';FM='Bancapp-Mono'
else:
    F='Helvetica';FB='Helvetica-Bold';FM='Courier'

styles={
    'body':ParagraphStyle('Body',fontName=F,fontSize=9.3,leading=14,textColor=INK,spaceAfter=8),
    'h1':ParagraphStyle('H1',fontName=FB,fontSize=19,leading=25,textColor=NAVY,spaceAfter=14,keepWithNext=True),
    'h2':ParagraphStyle('H2',fontName=FB,fontSize=12,leading=17,textColor=BLUE,spaceBefore=10,spaceAfter=7,keepWithNext=True),
    'table':ParagraphStyle('TableCell',fontName=F,fontSize=8.1,leading=11.5,textColor=INK),
    'th':ParagraphStyle('TableHeading',fontName=FB,fontSize=8.2,leading=11.5,textColor=colors.white),
    'code':ParagraphStyle('Code',fontName=FM,fontSize=7.7,leading=11,textColor=NAVY,backColor=PALE,borderPadding=9,spaceBefore=4,spaceAfter=10,splitLongWords=True),
    'small':ParagraphStyle('Small',fontName=F,fontSize=8,leading=12,textColor=MUTED,spaceAfter=8),
    'step':ParagraphStyle('Step',fontName=F,fontSize=9.3,leading=14,textColor=INK,leftIndent=19,firstLineIndent=-17,spaceAfter=7),
}

def inline(text):
    text=escape(text).replace('\u2011','-').replace('\u2013','-').replace('\u2014','-')
    text=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',text)
    text=re.sub(r'`([^`]+)`',lambda m:'<font name="'+FM+'">'+m.group(1)+'</font>',text)
    return text.replace('\n','<br/>')

def P(text,style='body'):return Paragraph(inline(text),styles[style])

def grid(rows,widths=None,padding=7):
    if widths is None:
        fractions={2:[.27,.73],3:[.26,.31,.43],4:[.20,.19,.27,.34],5:[.20,.16,.19,.20,.25]}.get(len(rows[0]),[1/len(rows[0])]*len(rows[0]))
        widths=[CW*f for f in fractions]
    table=Table([[P(cell,'th' if i==0 else 'table') for cell in row] for i,row in enumerate(rows)],colWidths=widths,repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),
        ('LINEBELOW',(0,0),(-1,0),.6,BLUE),('LINEBELOW',(0,1),(-1,-1),.3,LINE),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),padding),('BOTTOMPADDING',(0,0),(-1,-1),padding),
        ('SPACEAFTER',(0,0),(-1,-1),10),
    ]))
    return [table,Spacer(1,10)]

class Manual(BaseDocTemplate):
    def __init__(self,*args,**kw):
        super().__init__(*args,**kw)
        self.addPageTemplates(PageTemplate('Bancapp',frames=[Frame(LEFT,BOTTOM,CW,HEIGHT-TOP-BOTTOM,id='main',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=self.chrome))
        self.chapter=0
    def beforeDocument(self):self.chapter=0
    def afterFlowable(self,flow):
        if isinstance(flow,Paragraph) and getattr(flow,'toc_level',None) is not None:
            key=flow.bookmark
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flow.getPlainText(),key,level=flow.toc_level,closed=flow.toc_level>0)
            self.notify('TOCEntry',(flow.toc_level,flow.getPlainText(),self.page,key))
    def chrome(self,c,doc):
        c.saveState()
        if doc.page>1:
            c.drawImage(str(ROOT/'app/static/bancapp-logo.png'),LEFT,HEIGHT-47,width=120,height=32.6,mask='auto')
            c.setFont(F,8);c.setFillColor(MUTED);c.drawRightString(WIDTH-RIGHT,HEIGHT-32,'DELIVERY DESK  /  RELEASE 4.1')
            c.setStrokeColor(LINE);c.setLineWidth(.6);c.line(LEFT,HEIGHT-58,WIDTH-RIGHT,HEIGHT-58)
        c.setStrokeColor(LINE);c.line(LEFT,35,WIDTH-RIGHT,35)
        c.setFillColor(MUTED);c.setFont(F,7.2);c.drawString(LEFT,23,'Bancapp Automation Pvt Ltd  |  Internal deployment and operating guide')
        c.drawRightString(WIDTH-RIGHT,23,str(doc.page));c.restoreState()

story=[];heading_id=0
def heading(text,level=0,newpage=True):
    global heading_id
    if level==0 and newpage:story.append(PageBreak())
    h=P(text,'h1' if level==0 else 'h2');h.toc_level=level;h.bookmark='section-'+str(heading_id);heading_id+=1;story.append(h)

def markdown(text,prefix=''):
    lines=text.splitlines();i=0;first=True
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('```'):
            code=[];i+=1
            while i<len(lines) and not lines[i].startswith('```'):code.append(lines[i]);i+=1
            # Each command wraps independently; preserve spaces without forcing overflow.
            for command in code:story.append(P(command,'code'))
            i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                row=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',x.replace(' ','')) for x in row):rows.append(row)
                i+=1
            story.extend(grid(rows));continue
        if line.startswith('# '):heading(prefix+line[2:],0);i+=1;continue
        if line.startswith('## '):heading(line[3:],1,False);i+=1;continue
        if re.match(r'^\d+\. ',line) or line.startswith('- '):story.append(P(line,'step'));i+=1;continue
        para=[line];i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||```|\d+\. |\- )',lines[i].strip()):para.append(lines[i].strip());i+=1
        story.append(P(' '.join(para)))

# Cover
story += [Spacer(1,17),Image(str(ROOT/'app/static/bancapp-logo.png'),width=260,height=70.6,hAlign='LEFT'),Spacer(1,38)]
story.append(Paragraph('DELIVERY DESK',ParagraphStyle('CoverKicker',fontName=FB,fontSize=12,leading=17,textColor=BLUE,spaceAfter=14)))
story.append(Paragraph('Deployment, Features<br/>&amp; SOP Manual',ParagraphStyle('CoverTitle',fontName=FB,fontSize=31,leading=39,textColor=NAVY,spaceAfter=20)))
story.append(Paragraph('Bug tracking. Request delivery.<br/>Verified resolutions and L1 support.',ParagraphStyle('CoverSub',fontName=F,fontSize=14,leading=22,textColor=MUTED,spaceAfter=30)))
story.extend(grid([['Release','Prepared','Audience'],['4.1 | Schema 6','18 November 2026','Business teams, managers, Admin and infrastructure owners']],[CW*.23,CW*.25,CW*.52]))
story.append(Spacer(1,18));story.append(P('PostgreSQL + FastAPI + Docker Compose','h2'))
story.append(P('Includes complete features, role-based SOPs, notification administration, production handover, backup/recovery and field-by-field lifecycle reference.'))
story.append(Spacer(1,18));story.append(P('Transforming complex data into seamless efficiency.','small'))
story.append(P('Deployment review and UAT release. Target-host container execution and live integrations require acceptance checks.','small'))
story.append(PageBreak());story.append(P('Contents','h1'))
toc=TableOfContents();toc.levelStyles=[ParagraphStyle('TOC0',fontName=FB,fontSize=10,leading=15,textColor=NAVY,spaceBefore=7),ParagraphStyle('TOC1',fontName=F,fontSize=8.5,leading=12,textColor=MUTED,leftIndent=13,spaceBefore=2)]
story.append(toc)
markdown((ROOT/'docs/MANUAL_SOURCE.md').read_text())
markdown((ROOT/'docs/DEPLOYMENT.md').read_text())
heading('Appendix A - complete field lifecycle reference')
story.append(P('The following 99 source/lifecycle reference fields are reproduced from the package field matrix, including business justification and acceptance criteria for non-bug requests. Workflow identity, mandatory developer resolution/RCA and measured-cycle records are listed separately. Required fields vary by request type, route, environment and impact; later-stage fields are not all entered at intake.'))
rows=list(csv.DictReader((ROOT/'docs/FIELD_LIFECYCLE_MATRIX.csv').open()))
for item in [('Business Justification','business_justification'),('Acceptance Criteria','acceptance_criteria')]:
    if item[1] not in {row['Key'] for row in rows}:
        rows.append({'Field':item[0],'Key':item[1],'Stage':'Reporting / triage','Responsible person':'Reporter / authorised editor','Rule':'Required for New Requirement, Feature Request and Change Request; separate from bug reproduction.'})
cells=[['Field / stored key','Stage / owner','Rule or evidence condition']]
for row in rows:
    cells.append([row['Field']+'\n'+row['Key'],row['Stage']+'; '+row['Responsible person'],row['Rule']])
story.extend(grid(cells,[CW*.34,CW*.28,CW*.38],padding=6))
heading('Appendix B - workflow and administration reference')
story.extend(grid([
    ['Record/control','Operational meaning'],
    ['Named workflow identity','Reporter, developer, designated tester, current tray owner, reported-against developer, followers/participants use user IDs.'],
    ['Developer resolution / RCA','Separate mandatory developer action inputs; author and correction cycle are retained.'],
    ['Measured work cycle','Assignment, response deadline/first response, fix submission and return/verification events support metrics and SLA attribution.'],
    ['Knowledge visibility','Internal by default; only Admin/Super Admin approves client-specific or global external publication.'],
    ['Notification permissions','manage_notifications; edit_notification_templates; manage_notification_overrides. Existing role and user overrides govern delegation.'],
    ['General permissions','raise, edit, reassign, fix, test_close, comment, attach, reports, performance, manage_users, manage_masters, manage_integrations, manage_releases, publish_knowledge, manage_rights. Workflow/client gates still apply.'],
    ['Session/access controls','Named login, hashed passwords, HTTP-only session cookie, CSRF checks for changes and server-side permissions. Secure cookies require HTTPS. No SSO/MFA is bundled.'],
    ['Evidence categories','Media and supporting documents remain linked to the parent issue; downloads recheck issue access.'],
    ['Retention','No automatic record/attachment purge or backup-retention job is installed; adopt a Bancapp retention policy and reviewed implementation.'],
]))
heading('Appendix C - verification and release record')
story.append(P('96 automated checks passed for this handover: the previous 89 backend checks plus seven deployment-helper safeguard checks. PostgreSQL/HTTP tests use a real disposable database; outbound email/model calls are simulated. Helper tests simulate Docker command results and do not prove a live container recovery.'))
story.append(P('Frontend rendering and offline preview-controller checks passed. Base/HTTPS Compose YAML parses; source and operational helpers compile. The PDF is generated from the shipped manual sources and field matrix, with branded pagination and contents. Container image build, target-host startup, full browser UAT, actual Outlook/Azure delivery, live AI calls, load/sizing and a Docker-volume restore rehearsal remain acceptance tasks.'))
story.extend(grid([['Record','Value'],['Application release','4.1.0'],['Database migration level','6'],['Prepared for','Bancapp Automation Pvt Ltd'],['Document date','18 November 2026'],['Source of truth','Application modules plus docs/MANUAL_SOURCE.md, docs/DEPLOYMENT.md and docs/FIELD_LIFECYCLE_MATRIX.csv'],['Open acceptance gates','Target-host Docker, TLS, real integration delivery, authenticated browser UAT, recovery and capacity sign-off']]))
DEST.parent.mkdir(exist_ok=True)
doc=Manual(str(DEST),pagesize=A4,title='Bancapp Delivery Desk - Deployment, Features and SOP Manual',author='Bancapp Automation Pvt Ltd',subject='Release 4.1: PostgreSQL Docker deployment and operating procedures')
doc.multiBuild(story)
print(DEST)
