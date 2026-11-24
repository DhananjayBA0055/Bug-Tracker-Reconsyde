"""Branded server-side Excel/PDF exports, independent of browser printing."""
from io import BytesIO
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.drawing.image import Image
from openpyxl.utils import get_column_letter
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image as PDFImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR=Path(__file__).parent/'fonts'
if (FONT_DIR/'DejaVuSans.ttf').exists():
    pdfmetrics.registerFont(TTFont('Bancapp',str(FONT_DIR/'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('Bancapp-Bold',str(FONT_DIR/'DejaVuSans-Bold.ttf')))
    pdfmetrics.registerFontFamily('Bancapp',normal='Bancapp',bold='Bancapp-Bold',italic='Bancapp',boldItalic='Bancapp-Bold')

LOGO=Path(__file__).parent/'static/bancapp-logo.png'
NAVY='122F70';BLUE='397CDD';PALE='EAF1FD'
def excel(title,headers,rows):
    wb=Workbook();ws=wb.active;ws.title='Report';n=max(2,len(headers))
    ws.merge_cells(start_row=4,start_column=1,end_row=4,end_column=n)
    ws.cell(4,1,'BancApp Automation | '+title).font=Font(size=18,bold=True,color=NAVY)
    ws.cell(4,1).alignment=Alignment(vertical='center',indent=1);ws.row_dimensions[1].height=24;ws.row_dimensions[2].height=24;ws.row_dimensions[4].height=30
    if LOGO.exists():
        im=Image(str(LOGO));im.width=166;im.height=45;ws.add_image(im,'A1')
    ws.merge_cells(start_row=5,start_column=1,end_row=5,end_column=n)
    ws.cell(5,1,'Delivery Desk | Generated '+datetime.now().astimezone().strftime('%d %b %Y %H:%M %Z')).font=Font(size=10,color='65758F')
    for j,h in enumerate(headers,1):
        c=ws.cell(7,j,str(h));c.fill=PatternFill('solid',fgColor=NAVY);c.font=Font(color='FFFFFF',bold=True);c.alignment=Alignment(wrap_text=True,vertical='center')
        ws.column_dimensions[get_column_letter(j)].width=min(70,max(18,len(str(h))+4))
    ws.row_dimensions[7].height=32
    for i,row in enumerate(rows,8):
        for j,value in enumerate(row,1):
            value='' if value is None else value
            if isinstance(value,datetime):value=value.isoformat()
            if isinstance(value,(dict,list)):value=str(value)
            c=ws.cell(i,j,value)
            if isinstance(value,str):c.data_type='s' # Uploaded or bug text must never become executable formulas.
            c.font=Font(size=10,color='25344D');c.alignment=Alignment(vertical='top',wrap_text=True)
            if i%2==0:c.fill=PatternFill('solid',fgColor='F1F5FB')
        ws.row_dimensions[i].height=min(150,max(30,max((len(str(v or ''))//45+1)*14 for v in row)))
    ws.freeze_panes='B8';ws.auto_filter.ref=f'A7:{get_column_letter(len(headers))}{max(7,ws.max_row)}'
    ws.print_title_rows='1:7';ws.sheet_properties.pageSetUpPr.fitToPage=True;ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A4;ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=0
    ws.oddFooter.center.text='BancApp Automation | Confidential | Page &P of &N'
    out=BytesIO();wb.save(out);return out.getvalue()

def pdf(title,headers,rows):
    out=BytesIO();pagesize=landscape(A4) if len(headers)>4 else A4
    doc=SimpleDocTemplate(out,pagesize=pagesize,rightMargin=30,leftMargin=30,topMargin=80,bottomMargin=38)
    styles=getSampleStyleSheet();style=styles['BodyText'];style.fontSize=8;style.leading=12;style.fontName='Bancapp'
    head=styles['Heading2'];head.fontName='Bancapp-Bold';head.textColor=colors.HexColor('#'+NAVY)
    def para(v):return Paragraph(escape(str(v if v is not None else '')).replace('\n','<br/>'),style)
    def frame(canvas,document):
        canvas.saveState();w,h=pagesize
        if LOGO.exists():canvas.drawImage(str(LOGO),30,h-57,width=145,height=40,preserveAspectRatio=True,mask='auto')
        canvas.setFillColor(colors.HexColor('#'+NAVY));canvas.setFont('Bancapp-Bold',11);canvas.drawRightString(w-30,h-36,title[:80])
        canvas.setFont('Bancapp',8);canvas.setFillColor(colors.HexColor('#68778D'));canvas.drawRightString(w-30,h-51,datetime.now().astimezone().strftime('%d %b %Y %H:%M %Z'))
        canvas.setStrokeColor(colors.HexColor('#DCE6F7'));canvas.line(30,h-67,w-30,h-67)
        canvas.setFont('Bancapp',8);canvas.drawString(30,22,'BancApp Automation | Delivery Desk | Confidential');canvas.drawRightString(w-30,22,f'Page {document.page}');canvas.restoreState()
    story=[]
    if not rows:story=[Paragraph('No records match the selected filters.',style)]
    # Wide reports use repeated identifier columns across sections, avoiding unreadable 15-column PDFs.
    groups=[list(range(len(headers)))] if len(headers)<=7 else [[0]+list(range(i,min(i+6,len(headers)))) for i in range(1,len(headers),6)]
    for group_index,cols in enumerate(groups):
        if group_index:story.append(PageBreak())
        story.append(Paragraph(escape(title)+(f' — section {group_index+1}' if len(groups)>1 else ''),head));story.append(Spacer(1,12))
        table_rows=[[para(headers[i]) for i in cols]]
        # Split long cell text into bounded chunks so one row can never exceed a PDF page.
        for row in rows:
            values=[str(row[i] if row[i] is not None else '') for i in cols]
            chunks=max(1,max((len(v)+449)//450 for v in values))
            for part in range(chunks):table_rows.append([para(v[part*450:(part+1)*450] if k else v if part==0 else '↳ continued') for k,v in enumerate(values)])
        widths=[(pagesize[0]-60)/len(cols)]*len(cols)
        table=Table(table_rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#'+PALE)),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,0),1,colors.HexColor('#'+BLUE)),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F5F8FD')]),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#E1E7F1'))]))
        story.append(table)
    doc.build(story,onFirstPage=frame,onLaterPages=frame);return out.getvalue()

def dashboard_pdf(sections):
    """Continuous branded dashboard report with global pagination and no omitted sections."""
    out=BytesIO();pagesize=landscape(A4)
    doc=SimpleDocTemplate(out,pagesize=pagesize,leftMargin=30,rightMargin=30,topMargin=80,bottomMargin=38)
    styles=getSampleStyleSheet();body=styles['BodyText'];body.fontName='Bancapp';body.fontSize=8;body.leading=12
    heading=styles['Heading2'];heading.fontName='Bancapp-Bold';heading.fontSize=12;heading.textColor=colors.HexColor('#'+NAVY);heading.keepWithNext=True
    def para(v):return Paragraph(escape(str(v if v is not None else '')).replace('\n','<br/>'),body)
    def frame(canvas,document):
        canvas.saveState();w,h=pagesize
        if LOGO.exists():canvas.drawImage(str(LOGO),30,h-57,width=145,height=40,preserveAspectRatio=True,mask='auto')
        canvas.setFillColor(colors.HexColor('#'+NAVY));canvas.setFont('Bancapp-Bold',12);canvas.drawRightString(w-30,h-36,'Management dashboard | Complete report')
        canvas.setFont('Bancapp',8);canvas.setFillColor(colors.HexColor('#68778D'));canvas.drawRightString(w-30,h-51,datetime.now().astimezone().strftime('%d %b %Y %H:%M %Z'))
        canvas.setStrokeColor(colors.HexColor('#DCE6F7'));canvas.line(30,h-67,w-30,h-67)
        canvas.drawString(30,22,'BancApp Automation | Delivery Desk | Confidential');canvas.drawRightString(w-30,22,f'Page {document.page}');canvas.restoreState()
    story=[]
    for title,headers,rows in sections:
        groups=[list(range(len(headers)))] if len(headers)<=7 else [[0]+list(range(i,min(i+6,len(headers)))) for i in range(1,len(headers),6)]
        for n,cols in enumerate(groups):
            story.append(Paragraph(escape(title)+(f' — detail {n+1}' if len(groups)>1 else ''),heading))
            if not rows:story.extend([para('No matching records.'),Spacer(1,12)]);continue
            table_rows=[[para(headers[i]) for i in cols]]
            for row in rows:
                values=[str(row[i] if row[i] is not None else '') for i in cols]
                chunks=max(1,max((len(v)+449)//450 for v in values))
                for part in range(chunks):table_rows.append([para(v[part*450:(part+1)*450] if k else v if part==0 else 'continued') for k,v in enumerate(values)])
            table=Table(table_rows,colWidths=[(pagesize[0]-60)/len(cols)]*len(cols),repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#'+PALE)),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F5F8FD')]),('LINEBELOW',(0,0),(-1,0),1,colors.HexColor('#'+BLUE)),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#E1E7F1'))]))
            story.extend([table,Spacer(1,18)])
    doc.build(story,onFirstPage=frame,onLaterPages=frame);return out.getvalue()
