import csv,io,json,re
from datetime import datetime,timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Form,Response
from pydantic import BaseModel,Field
from psycopg.types.json import Jsonb
from openpyxl import load_workbook
from . import main as m
from .permissions import ROLES,TEAMS,BASE,PERMISSIONS,effective,team_for
from .notifications import encrypt,send,queue
from .reporting import excel

router=APIRouter(prefix='/api')
EMAIL=re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
USER_COLUMNS=['email','name','role','team','manager_emails','clients','active','permissions','password']

class UserBody(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    name:str=Field(min_length=1,max_length=100)
    role:str
    team:str=''
    manager_emails:list[str]=[]
    clients:list[str]=[]
    permissions:dict[str,bool]={}
    password:str=Field(default='',max_length=1024)
    active:bool=True

def validate_user(body,actor,old=None):
    if body.role not in ROLES or not EMAIL.fullmatch(body.email):raise HTTPException(422,'Choose a valid email and business role')
    if body.role=='super_admin' and actor['role']!='super_admin':raise HTTPException(403,'Only a Super Admin can create or edit Super Admin access')
    if old and old['role']=='super_admin' and actor['role']!='super_admin':raise HTTPException(403,'Super Admin accounts are protected')
    if not old and len(body.password)<12 or body.password and len(body.password)<12:raise HTTPException(422,'New or reset passwords need at least 12 characters')
    if set(body.permissions)-set(PERMISSIONS):raise HTTPException(422,'Unknown permission key')
    if actor['role']!='super_admin' and body.role=='super_admin':raise HTTPException(403,'Super Admin access is protected')
    if body.team and body.team not in TEAMS:raise HTTPException(422,'Choose Process Team, Product Team or QA Team')
    if body.role=='client' and (not body.clients or any(x in {'All','(All tenants)'} for x in body.clients)):raise HTTPException(422,'Client accounts need explicit client names')
    if any(not EMAIL.fullmatch(e) for e in body.manager_emails):raise HTTPException(422,'Manager email format is invalid')

def upsert(c,body,actor,old=None):
    validate_user(body,actor,old)
    if old:
        if old['role']=='super_admin' and old['active'] and (not body.active or body.role!='super_admin'):
            if c.execute("SELECT count(*) AS n FROM users WHERE role='super_admin' AND active=true").fetchone()['n']<=1:raise HTTPException(422,'Keep at least one active Super Admin')
        c.execute('UPDATE users SET email=%s,name=%s,role=%s,team=%s,manager_emails=%s,clients=%s,permissions=%s,active=%s,password_hash=%s WHERE id=%s',
                  (body.email.lower(),body.name,body.role,body.team or team_for(body.role),Jsonb(body.manager_emails),Jsonb(body.clients),Jsonb(body.permissions),body.active,m.hash_password(body.password) if body.password else old['password_hash'],old['id']))
        c.execute('DELETE FROM sessions WHERE user_id=%s',(old['id'],));uid=old['id']
    else:
        uid=c.execute('INSERT INTO users(email,name,password_hash,role,team,manager_emails,clients,permissions,active) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',
                      (body.email.lower(),body.name,m.hash_password(body.password),body.role,body.team or team_for(body.role),Jsonb(body.manager_emails),Jsonb(body.clients),Jsonb(body.permissions),body.active)).fetchone()['id']
    m.audit(c,actor['email'],'User access updated' if old else 'User created',changes={'email':body.email,'role':body.role,'team':body.team,'active':body.active,'permissions':body.permissions})
    row=c.execute('SELECT * FROM users WHERE id=%s',(uid,)).fetchone();row['_permissions']=effective(row,m.setting(c,'role_permissions'));return m.public_user(row)

@router.get('/users')
def users(u=Depends(m.auth)):
    if u['role']!='manager':m.require_action(u,'manage_users')
    with m.db() as c:
        configured=m.setting(c,'role_permissions');rows=c.execute('SELECT * FROM users ORDER BY name').fetchall()
        for row in rows:row['_permissions']=effective(row,configured)
        return [m.public_user(row) for row in rows]

@router.post('/users',status_code=201)
def create(body:UserBody,u=Depends(m.auth)):
    m.require_action(u,'manage_users')
    with m.db() as c:
        c.execute('SELECT pg_advisory_xact_lock(934929)')
        if c.execute('SELECT 1 FROM users WHERE email=%s',(body.email.lower(),)).fetchone():raise HTTPException(409,'Email already exists')
        return upsert(c,body,u)

@router.put('/users/{uid}')
def update(uid:int,body:UserBody,u=Depends(m.auth)):
    m.require_action(u,'manage_users')
    with m.db() as c:
        c.execute('SELECT pg_advisory_xact_lock(934929)')
        old=c.execute('SELECT * FROM users WHERE id=%s FOR UPDATE',(uid,)).fetchone()
        if not old:raise HTTPException(404,'User not found')
        if c.execute('SELECT 1 FROM users WHERE email=%s AND id<>%s',(body.email.lower(),uid)).fetchone():raise HTTPException(409,'Email already exists')
        return upsert(c,body,u,old)

def read_rows(name,data):
    if len(data)>20*1024*1024:raise HTTPException(413,'Bulk upload limit is 20 MB')
    if name.lower().endswith('.csv'):
        try:rows=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
        except (UnicodeDecodeError,csv.Error):raise HTTPException(422,'Use a UTF-8 CSV file')
    elif name.lower().endswith('.xlsx'):
        import zipfile
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if sum(x.file_size for x in z.infolist())>50*1024*1024:raise HTTPException(413,'Expanded workbook is too large')
            wb=load_workbook(io.BytesIO(data),read_only=True,data_only=False);ws=wb.active
            iterator=ws.iter_rows(values_only=True);headers=[str(v or '').strip() for v in next(iterator)]
            rows=[dict(zip(headers,r)) for r in iterator if any(v is not None for v in r)]
            wb.close()
        except HTTPException:raise
        except Exception:raise HTTPException(422,'Cannot read XLSX workbook')
    else:raise HTTPException(422,'Upload CSV or XLSX')
    if not rows or len(rows)>1000:raise HTTPException(422,'Use 1–1,000 rows per bulk upload')
    return [{str(k).strip().lower():v for k,v in row.items() if k is not None} for row in rows]

def split(v):return [s.strip() for s in str(v or '').split(';') if s.strip()]
def user_from_row(row):
    rights=row.get('permissions') or '{}'
    try:rights=json.loads(rights) if isinstance(rights,str) else rights
    except ValueError:raise HTTPException(422,'Permissions must be a JSON object such as {"raise":true}')
    return UserBody(email=str(row.get('email') or '').strip().lower(),name=str(row.get('name') or '').strip(),role=str(row.get('role') or '').strip(),team=str(row.get('team') or '').strip(),manager_emails=split(row.get('manager_emails')),clients=split(row.get('clients')),permissions=rights,password=str(row.get('password') or ''),active=str(row.get('active','true')).lower() not in {'false','0','no'})

@router.get('/bulk/template/{kind}')
def template(kind:str,u=Depends(m.auth)):
    csv_format=kind.endswith('.csv');kind=kind.removesuffix('.csv').removesuffix('.xlsx')
    m.require_action(u,'manage_users' if kind=='users' else 'manage_masters')
    if kind=='users':headers=USER_COLUMNS;rows=[]
    elif kind=='masters':headers=['group','operation','value','new_value'];rows=[]
    else:raise HTTPException(404,'Unknown template')
    if csv_format:
        out=io.StringIO();writer=csv.writer(out);writer.writerow(headers)
        return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="Bancapp_{kind}_template.csv"'})
    data=excel('Bulk '+kind+' upload template',headers,rows)
    # Import expects headers in row 1, unlike branded report worksheets.
    from openpyxl import Workbook
    w=Workbook();ws=w.active;ws.title='Upload';ws.append(headers)
    from openpyxl.styles import Font,PatternFill
    for cell in ws[1]:cell.font=Font(color='FFFFFF',bold=True);cell.fill=PatternFill('solid',fgColor='122F70');ws.column_dimensions[cell.column_letter].width=24
    out=io.BytesIO();w.save(out)
    return Response(out.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="Bancapp_{kind}_template.xlsx"'})

@router.post('/bulk/users')
async def bulk_users(file:UploadFile=File(...),apply:bool=Form(False),u=Depends(m.auth)):
    m.require_action(u,'manage_users');rows=read_rows(file.filename or '',await file.read(20*1024*1024+1));errors=[];preview=[];valid=[];seen=set()
    with m.db() as c:
        c.execute('SELECT pg_advisory_xact_lock(934929)')
        for i,row in enumerate(rows,2):
            try:
                b=user_from_row(row)
                if b.email in seen:raise HTTPException(422,'Duplicate email in upload')
                seen.add(b.email);old=c.execute('SELECT * FROM users WHERE email=%s',(b.email,)).fetchone();validate_user(b,u,old)
                valid.append((b,old));preview.append({'row':i,'email':b.email,'name':b.name,'role':b.role,'operation':'update' if old else 'create'})
            except Exception as e:errors.append({'row':i,'error':str(e.detail) if isinstance(e,HTTPException) else 'Invalid row values'})
        if apply and errors:raise HTTPException(422,{'message':'Nothing was changed; correct all rows first','errors':errors})
        if apply:
            for body,old in valid:upsert(c,body,u,old)
        return {'applied':apply,'rows':preview,'errors':errors,'count':len(valid)}

def edit_master(lists,group,operation,value,new_value='',replacement=None):
    if group not in lists:raise HTTPException(422,'Unknown dropdown group')
    values=lists[group]
    if operation=='modify' and replacement is not None:
        if any(not isinstance(x,str) or not x.strip() or len(x)>200 for x in replacement) or len(set(replacement))!=len(replacement):raise HTTPException(422,'Use unique nonempty values, one per line')
        protected=set(values) if group in {'Severity','Yes/No','Team','Issue Type'} else set(values)&{'New','In Progress','In QA','Closed','Reopened','Ready for Deployment','Ready for Closure','Duplicate'} if group=='Status' else set()
        if not protected<=set(replacement):raise HTTPException(422,'Required workflow and request-type values cannot be removed')
        lists[group]=replacement;return lists
    if operation=='modify':operation='rename'
    if operation=='add':
        if not value or value in values:raise HTTPException(422,'New dropdown value must be unique and nonempty')
        values.append(value)
    elif operation in {'delete','rename'}:
        if value not in values:raise HTTPException(422,'Dropdown value not found')
        if group=='Status' and value in {'New','In Progress','In QA','Closed','Reopened','Ready for Deployment','Ready for Closure','Duplicate'}:raise HTTPException(422,'This state is required by the enforced workflow')
        if group in {'Severity','Yes/No','Team'}:raise HTTPException(422,'This policy list is structural; use SLA settings or user-team controls')
        if operation=='delete':values.remove(value)
        else:
            if not new_value or new_value in values:raise HTTPException(422,'Replacement value must be unique and nonempty')
            values[values.index(value)]=new_value
    else:raise HTTPException(422,'Operation must be add, rename or delete')
    return lists

class MasterEdit(BaseModel):
    group:str;operation:str;values:list[str]|None=None;value:str=Field(default='',max_length=200);new_value:str=Field(default='',max_length=200)
@router.post('/masters')
def masters(body:MasterEdit,u=Depends(m.auth)):
    m.require_action(u,'manage_masters')
    with m.db() as c:
        c.execute("SELECT data FROM settings WHERE key='lists' FOR UPDATE")
        data=edit_master(m.setting(c,'lists'),body.group,body.operation,body.value,body.new_value,body.values)
        c.execute("UPDATE settings SET data=%s WHERE key='lists'",(Jsonb(data),));m.audit(c,u['email'],'Dropdown changed',changes=body.model_dump());return {'ok':True}

@router.post('/bulk/masters')
async def bulk_masters(file:UploadFile=File(...),apply:bool=Form(False),u=Depends(m.auth)):
    m.require_action(u,'manage_masters');rows=read_rows(file.filename or '',await file.read(20*1024*1024+1));errors=[]
    with m.db() as c:
        c.execute("SELECT data FROM settings WHERE key='lists' FOR UPDATE");data=m.setting(c,'lists')
        for i,r in enumerate(rows,2):
            try:edit_master(data,str(r.get('group') or ''),str(r.get('operation') or 'add'),str(r.get('value') or ''),str(r.get('new_value') or ''))
            except HTTPException as e:errors.append({'row':i,'error':e.detail})
        if apply and errors:raise HTTPException(422,{'message':'Nothing was changed','errors':errors})
        if apply:
            c.execute("UPDATE settings SET data=%s WHERE key='lists'",(Jsonb(data),));m.audit(c,u['email'],'Dropdown bulk upload',changes={'rows':len(rows)})
        return {'applied':apply,'rows':rows,'errors':errors,'count':len(rows)-len(errors)}

class RightsBody(BaseModel):
    roles:dict[str,list[str]]
@router.put('/rights')
def rights(body:RightsBody,u=Depends(m.auth)):
    m.require_action(u,'manage_rights')
    if set(body.roles)!=set(ROLES) or any(set(v)-set(PERMISSIONS) for v in body.roles.values()):raise HTTPException(422,'Use defined roles and permission keys')
    if set(body.roles['super_admin'])!=set(PERMISSIONS):raise HTTPException(422,'Super Admin must retain all rights')
    if 'manage_users' not in body.roles['admin'] or 'manage_rights' not in body.roles['admin']:raise HTTPException(422,'Admin must retain user and rights management')
    with m.db() as c:
        c.execute("UPDATE settings SET data=%s WHERE key='role_permissions'",(Jsonb(body.roles),));m.audit(c,u['email'],'Role permissions changed',changes=body.roles)
    return {'ok':True}

def public_config(data):return {**{k:v for k,v in data.items() if k not in {'secret','api_key'}},'has_secret':bool(data.get('secret') or data.get('api_key'))}
@router.get('/connections/{kind}')
def connections(kind:str,u=Depends(m.auth)):
    m.require_action(u,'manage_integrations')
    if kind not in {'mail','ai'}:raise HTTPException(404,'Unknown connection')
    with m.db() as c:return public_config(m.setting(c,kind))

class ConnectionBody(BaseModel):
    data:dict
@router.put('/connections/{kind}')
def save_connection(kind:str,body:ConnectionBody,u=Depends(m.auth)):
    m.require_action(u,'manage_integrations');data=dict(body.data)
    if kind not in {'mail','ai'}:raise HTTPException(404,'Unknown connection')
    with m.db() as c:
        old=m.setting(c,kind);allowed={'mail':{'enabled','transport','sender','manager_cc','day_end_hour','day_end_minute','timezone','app_url','tenant_id','client_id','host','port','username','secret'},'ai':{'provider','model','endpoint','api_key'}}[kind]
        if set(data)-allowed:raise HTTPException(422,'Unknown configuration fields')
        config={**old,**{k:v for k,v in data.items() if k not in {'secret','api_key'}}}
        for k in {'secret','api_key'}&allowed:
            if data.get(k):
                try:config[k]=encrypt(str(data[k]))
                except ValueError as e:raise HTTPException(422,str(e))
        if kind=='mail':
            if config.get('transport') not in {'graph','smtp_starttls','smtp_ssl'}:raise HTTPException(422,'Choose Microsoft Graph or TLS-enabled SMTP')
            if not 0<=int(config.get('day_end_hour',18))<=23 or not 0<=int(config.get('day_end_minute',0))<=59:raise HTTPException(422,'Invalid report time')
            try:ZoneInfo(config.get('timezone','Asia/Kolkata'))
            except Exception:raise HTTPException(422,'Invalid timezone')
            if not isinstance(config.get('manager_cc',[]),list) or any(not EMAIL.fullmatch(str(x)) for x in config.get('manager_cc',[])):raise HTTPException(422,'Enter valid manager CC emails')
            if config.get('enabled'):
                if not EMAIL.fullmatch(str(config.get('sender',''))):raise HTTPException(422,'Sender email is required')
                if not config.get('manager_cc') and not c.execute("SELECT 1 FROM users WHERE role='manager' AND active=true").fetchone():raise HTTPException(422,'Configure a manager CC address or an active Manager user')
                if config['transport']=='graph' and not all(config.get(k) for k in ['tenant_id','client_id','secret']):raise HTTPException(422,'Microsoft Graph needs tenant ID, client ID and client secret')
                if config['transport']!='graph' and (not config.get('host') or not 1<=int(config.get('port',587))<=65535):raise HTTPException(422,'SMTP host and port are required')
        else:
            if config.get('provider') not in {'retrieval','azure_openai','openai'}:raise HTTPException(422,'Choose retrieval, Azure OpenAI or OpenAI')
            if config.get('provider')!='retrieval':
                if not config.get('api_key') or not config.get('model'):raise HTTPException(422,'Model/deployment and API key are required')
                if config['provider']=='azure_openai':
                    url=urlparse(config.get('endpoint',''))
                    if url.scheme!='https' or not url.hostname or not url.hostname.endswith(('.openai.azure.com','.services.ai.azure.com')) or url.username or url.password or url.query:raise HTTPException(422,'Use your HTTPS Azure OpenAI resource URL')
        c.execute('UPDATE settings SET data=%s WHERE key=%s',(Jsonb(config),kind));m.audit(c,u['email'],'Connection configured',changes={'kind':kind,'provider':config.get('provider',config.get('transport'))})
        return public_config(config)

class TestMail(BaseModel):
    recipient:str
@router.post('/connections/mail/test')
def test_mail(body:TestMail,u=Depends(m.auth)):
    m.require_action(u,'manage_integrations')
    if not EMAIL.fullmatch(body.recipient):raise HTTPException(422,'Enter a valid test recipient')
    with m.db() as c:
        cfg=m.setting(c,'mail')
        if not cfg.get('enabled'):raise HTTPException(422,'Enable and save the mail connection first')
        cc=cfg.get('manager_cc') or [r['email'] for r in c.execute("SELECT email FROM users WHERE role='manager' AND active=true").fetchall()]
        queue(c,'test:'+str(datetime.now(timezone.utc).timestamp()),[body.recipient],cc,'Bancapp Delivery Desk — connection test','Your configured delivery connection is ready for notification processing.')
        m.audit(c,u['email'],'Test email queued',changes={'recipient':body.recipient})
    return {'ok':True,'message':'Test message queued. Check the notification log for delivery status.'}

@router.get('/notifications')
def notification_log(u=Depends(m.auth)):
    m.require_action(u,'manage_integrations')
    with m.db() as c:return c.execute('SELECT id,recipients,cc,subject,status,attempts,last_error,created_at,sent_at FROM notification_outbox ORDER BY id DESC LIMIT 300').fetchall()
