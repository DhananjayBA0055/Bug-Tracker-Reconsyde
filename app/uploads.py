from pathlib import Path
from fastapi import HTTPException
EXTENSIONS={'.png','.jpg','.jpeg','.webp','.gif','.mp4','.webm','.mov','.doc','.docx','.xls','.xlsx','.csv','.pdf'}
def validate_attachment(name,content):
    suffix=Path(name).suffix.lower()
    if suffix not in EXTENSIONS:raise HTTPException(422,'Allowed: images, MP4/WebM/MOV, Word, Excel, CSV and PDF')
    if len(content)>20*1024*1024:raise HTTPException(413,'Maximum attachment size is 20 MB')
    if not content:raise HTTPException(422,'Attachment is empty')
    signatures={'.png':b'\x89PNG\r\n\x1a\n','.jpg':b'\xff\xd8','.jpeg':b'\xff\xd8','.pdf':b'%PDF-', '.docx':b'PK','.xlsx':b'PK','.doc':b'\xd0\xcf\x11\xe0','.xls':b'\xd0\xcf\x11\xe0'}
    if suffix in signatures and not content.startswith(signatures[suffix]):raise HTTPException(422,'The file contents do not match its extension')
    if suffix=='.webp' and not (content.startswith(b'RIFF') and content[8:12]==b'WEBP'):raise HTTPException(422,'Invalid WebP file')
    if suffix=='.gif' and not content.startswith((b'GIF87a',b'GIF89a')):raise HTTPException(422,'Invalid GIF file')
    if suffix in {'.mp4','.mov'} and b'ftyp' not in content[:32]:raise HTTPException(422,'Invalid MP4/MOV file')
    if suffix=='.webm' and not content.startswith(b'\x1aE\xdf\xa3'):raise HTTPException(422,'Invalid WebM file')
