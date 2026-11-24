from .clock import business_date
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from fastapi import FastAPI, Request, Response, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .domain import TERMINAL, EXTRA_FIELDS, INTAKE_DEFERRED_FIELDS, calculate, validate_patch
from .permissions import BASE,ROLES,ADMIN_ROLES,DEV_ROLES,effective
from . import workflow,lifecycle
from .request_types import kind as request_kind,summary as request_summary,PREFIXES,KINDS

ROOT=Path(__file__).resolve().parent.parent
SEED=json.loads((ROOT/'data/workbook.json').read_text())
FIELDS=[dict(f) for f in SEED['fields']]+[dict(zip(['key','label','type','options'],r)) for r in EXTRA_FIELDS+lifecycle.EXTRA]
for _f in FIELDS:
    if _f['key']=='browser_device':_f.update(type='select',options='Browser / Device')
    if _f['key']=='sprint':_f.update(type='select',options='Sprint / Iteration')
DB_URL=os.environ.get('DATABASE_URL','postgresql://tracker:tracker@localhost:5432/tracker')
COOKIE_SECURE=os.environ.get('COOKIE_SECURE','true').lower()=='true'
MAX_FILE=20*1024*1024
EDITORS={'super_admin','admin','product_developer','process_developer','process_designer','quality_analyst'}

FIELDS.append({'key':'source_solution_recommendation','label':'Historical Source Product Solution Recommendation','type':'computed','options':None})

def db(): return psycopg.connect(DB_URL,row_factory=dict_row,connect_timeout=10)
def setting(c,key): return c.execute('SELECT data FROM settings WHERE key=%s',(key,)).fetchone()['data']
def audit(c,actor,action,issue_id=None,changes=None):
    person=c.execute('SELECT id FROM users WHERE lower(email)=lower(%s)',(actor,)).fetchone();uid=person['id'] if person else None
    c.execute('INSERT INTO audit(actor,action,issue_id,changes,user_id) VALUES(%s,%s,%s,%s,%s)',(actor,action,issue_id,Jsonb(changes or {}),uid))
    if uid:c.execute("UPDATE users SET last_action_at=now(),last_login_at=CASE WHEN %s='Signed in' THEN now() ELSE last_login_at END WHERE id=%s",(action,uid))
def hash_password(password):
    salt=secrets.token_hex(16)
    return salt+':'+hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
def verify_password(password,stored):
    salt,want=stored.split(':')
    got=hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
    return hmac.compare_digest(got,want)
def public_user(u):
    result={k:u.get(k) for k in ['id','email','name','role','clients','active','team','manager_emails','permissions']}
    result['effective_permissions']=sorted(u.get('_permissions',effective(u)))
    return result

def require_action(u,action):
    if action not in u.get('_permissions',effective(u)):raise HTTPException(403,'Your account does not have the '+action+' permission')

def initialize():
    with db() as c:
        c.execute('SELECT pg_advisory_xact_lock(934928)')
        c.execute((ROOT/'app/schema.sql').read_text())
        if not c.execute('SELECT 1 FROM schema_versions WHERE version=2').fetchone():
            c.execute((ROOT/'app/migration_v2.sql').read_text())
        if not c.execute('SELECT 1 FROM schema_versions WHERE version=3').fetchone():c.execute((ROOT/'app/migration_v3.sql').read_text())
        if not c.execute('SELECT 1 FROM schema_versions WHERE version=4').fetchone():c.execute((ROOT/'app/migration_v4.sql').read_text())
        if not c.execute('SELECT 1 FROM schema_versions WHERE version=5').fetchone():c.execute((ROOT/'app/migration_v5.sql').read_text())
        notification_upgrade=not c.execute('SELECT 1 FROM schema_versions WHERE version=6').fetchone()
        if notification_upgrade:c.execute((ROOT/'app/migration_v6.sql').read_text())
        from .notification_policy import defaults as notification_defaults,PERMISSIONS as notification_permissions
        c.execute("INSERT INTO settings(key,data) VALUES('notification_policy',%s) ON CONFLICT DO NOTHING",(Jsonb(notification_defaults()),))
        lists=SEED['lists'].copy();lists['Team']=['Process Team','Product Team','QA Team']
        lists.update({'Issue Type':KINDS+['New requirement','change request'],'Bucket':['product','process'],
                      'Delivery Stage':['planning','Development','BA UAT','BA process dev','Client UAT','Client Production'],
                      'Browser / Device':['Chrome / Windows','Edge / Windows','Firefox / Windows','Safari / macOS','Mobile / Android','Mobile / iOS','Other'],
                      'Sprint / Iteration':[]})
        lists.update(lifecycle.POLICY_LISTS)
        lists['Status']=list(dict.fromkeys(lists['Status']+['Ready for Deployment','Ready for Closure']))
        # Preserve source spellings; display aliases can be reviewed by an administrator.
        for field in FIELDS:
            opt=field.get('options')
            if opt:
                lists.setdefault(opt,[])
                for issue in SEED['issues']:
                    val=issue.get(field['key'])
                    if val and val not in lists[opt]: lists[opt].append(val)
        initial={'lists':lists,'sla':SEED['sla'],'source_archive':SEED['source_snapshots'],
                 'comparison':SEED['comparison'],'template_releases':SEED['template_releases'],'role_permissions':BASE,'mail':{'enabled':False,'transport':'graph','sender':'','manager_cc':[],'day_end_hour':18,'day_end_minute':0,'timezone':'Asia/Kolkata','app_url':''},'ai':{'provider':'retrieval','model':'','endpoint':''}}
        for k,v in initial.items(): c.execute('INSERT INTO settings(key,data) VALUES(%s,%s) ON CONFLICT DO NOTHING',(k,Jsonb(v)))
        rights=setting(c,'role_permissions')
        if notification_upgrade:
            for role in ['admin','super_admin']:
                for permission in notification_permissions:
                    if permission not in rights[role]:rights[role].append(permission)
        c.execute("UPDATE settings SET data=%s WHERE key='role_permissions'",(Jsonb(rights),))
        existing_lists=setting(c,'lists');changed_lists=False
        for group in ['Browser / Device','Sprint / Iteration',*lifecycle.POLICY_LISTS]:
            if group not in existing_lists:existing_lists[group]=lists[group];changed_lists=True
        for status in ['Ready for Deployment','Ready for Closure']:
            if status not in existing_lists['Status']:existing_lists['Status'].append(status);changed_lists=True
        for item in KINDS:
            if item not in existing_lists['Issue Type']:existing_lists['Issue Type'].append(item);changed_lists=True
        if changed_lists:c.execute("UPDATE settings SET data=%s WHERE key='lists'",(Jsonb(existing_lists),))
        digest=hashlib.sha256((ROOT/'data/workbook.json').read_bytes()).hexdigest()
        if not c.execute('SELECT 1 FROM imports WHERE source_hash=%s',(digest,)).fetchone():
            for issue in SEED['issues']:
                c.execute('INSERT INTO issues(id,data) VALUES(%s,%s) ON CONFLICT DO NOTHING',(issue['bug_id'],Jsonb(issue)))
            c.execute("SELECT setval('bug_number',GREATEST((SELECT coalesce(max(substring(id from '[0-9]+$')::bigint),0)+1 FROM issues),1),false)")
            c.execute('INSERT INTO imports(source_hash,filename,issue_count) VALUES(%s,%s,%s)',(digest,SEED['source_file'],len(SEED['issues'])))
            audit(c,'System','Workbook imported',changes={'issues':99,'missing_status':57,'missing_severity':99,'template_releases_excluded':5})
        if not c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            password=os.environ.get('ADMIN_PASSWORD','')
            email=os.environ.get('ADMIN_EMAIL','').strip().lower()
            if len(password)<12 or '@' not in email: raise RuntimeError('Set ADMIN_EMAIL and ADMIN_PASSWORD (at least 12 characters) before first startup.')
            c.execute('INSERT INTO users(email,name,password_hash,role) VALUES(%s,%s,%s,%s)',(email,os.environ.get('ADMIN_NAME','Bancapp Administrator'),hash_password(password),'super_admin'))
            audit(c,email,'Administrator initialized')

@asynccontextmanager
async def lifespan(app):
    initialize()
    yield

app=FastAPI(title='Reconsyde Delivery Desk',version='4.1.0',lifespan=lifespan)

@app.middleware('http')
async def headers(request,call_next):
    if request.method in {'POST','PUT','PATCH','DELETE'}:
        length=request.headers.get('content-length')
        if length and int(length)>MAX_FILE+65536: return Response('Request too large',status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    if request.url.path.startswith('/api'): response.headers['Cache-Control']='no-store'
    return response

def auth(request: Request):
    token=request.cookies.get('tracker_session','')
    with db() as c:
        row=c.execute('SELECT u.*,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=%s AND s.expires_at>now() AND u.active=true',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not row: raise HTTPException(401,'Please sign in')
    with db() as c: row['_permissions']=effective(row,setting(c,'role_permissions'))
    if request.method not in {'GET','HEAD','OPTIONS'}:
        if not hmac.compare_digest(request.headers.get('x-csrf-token',''),row['csrf']): raise HTTPException(403,'Invalid session request token; refresh and retry')
    return row

def require(u,roles):
    roles=set(roles)
    if 'admin' in roles:roles.add('super_admin')
    if 'editor' in roles:roles.update(EDITORS)
    if 'viewer' in roles:roles.add('manager')
    if u['role'] not in roles: raise HTTPException(403,'Your role does not allow this action')
def can_read(u,data):
    if u['role']!='client': return True
    # A shared All-tenants issue is never exposed automatically to external clients.
    clients=[v.strip() for v in str(data.get('client') or '').split(',')]
    if any(v in {'All','(All tenants)'} for v in clients): return False
    return bool(set(clients)&set(u['clients']))
def get_issue(c,issue_id,u,lock=False):
    row=c.execute('SELECT * FROM issues WHERE id=%s'+(' FOR UPDATE' if lock else ''),(issue_id,)).fetchone()
    if not row or not can_read(u,row['data']): raise HTTPException(404,'Issue not found')
    return row
def release_map(c): return {r['id']:r['data'] for r in c.execute('SELECT * FROM releases').fetchall()}
def enrich(c,row):
    data=calculate(row['data'],setting(c,'sla'),release_map(c))
    source=data.get('source_metadata') or {}
    if not data.get('action_requested') and source.get('Action Requested'):data['action_requested']=source['Action Requested']
    recommendation=source.get('Product Solution Recommendation')
    if recommendation:
        data['source_solution_recommendation']=recommendation
        if recommendation==data.get('actual_result'):data['review_flags'].append('Imported Actual Result repeats the source product recommendation; verify observed symptoms')
        if recommendation==data.get('root_cause_summary') and not data.get('resolution_author_id'):data['review_flags'].append('Imported product recommendation is not a verified developer RCA')
    return {**data,'revision':row['revision'],'updated_at':row['updated_at'].isoformat()}
CLIENT_FIELDS={'bug_id','title','date_reported','source','client','client_ticket_ref','issue_type','environment','steps_to_reproduce','expected_result','actual_result','business_justification','acceptance_criteria','request_kind','severity','priority','status','open_closed','sla_status','due_date','resolved_date','age_days','target_fix_release','target_release_date','actual_fix_release','actual_release_date','client_confirmation','revision','updated_at'}
def visible(u,d): return {k:v for k,v in d.items() if k in CLIENT_FIELDS} if u['role']=='client' else d

class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=1024)

@app.get('/api/health')
def health():
    try:
        with db() as c: c.execute('SELECT 1')
        return {'status':'ok','database':'PostgreSQL'}
    except psycopg.Error: raise HTTPException(503,'Database unavailable')

@app.post('/api/login')
def login(body:Login,request:Request,response:Response):
    email=body.email.strip().lower(); ip=request.client.host if request.client else 'unknown'
    with db() as c:
        c.execute("DELETE FROM login_attempts WHERE created_at<now()-interval '1 day'")
        n=c.execute("SELECT count(*) AS n FROM login_attempts WHERE (email=%s OR ip=%s) AND created_at>now()-interval '15 minutes'",(email,ip)).fetchone()['n']
        if n>=20: raise HTTPException(429,'Too many attempts; retry after 15 minutes')
        user=c.execute('SELECT * FROM users WHERE email=%s AND active=true',(email,)).fetchone()
        valid=verify_password(body.password,user['password_hash']) if user else verify_password(body.password,'0'*32+':'+'0'*128)
        if not valid:
            c.execute('INSERT INTO login_attempts(email,ip) VALUES(%s,%s)',(email,ip)); c.commit()
            raise HTTPException(401,'Incorrect email or password')
        token=secrets.token_urlsafe(40); csrf=secrets.token_urlsafe(32)
        c.execute('DELETE FROM sessions WHERE expires_at<now()')
        c.execute('INSERT INTO sessions(token_hash,user_id,csrf,expires_at) VALUES(%s,%s,%s,%s)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],csrf,datetime.now(timezone.utc)+timedelta(hours=12)))
        user['_permissions']=effective(user,setting(c,'role_permissions'))
        audit(c,email,'Signed in')
    response.set_cookie('tracker_session',token,httponly=True,secure=COOKIE_SECURE,samesite='strict',max_age=43200,path='/')
    return {'user':public_user(user),'csrf':csrf}

@app.get('/api/me')
def me(u=Depends(auth)): return {'user':public_user(u),'csrf':u['csrf']}

@app.post('/api/logout')
def logout(request:Request,response:Response,u=Depends(auth)):
    with db() as c: c.execute('DELETE FROM sessions WHERE token_hash=%s',(hashlib.sha256(request.cookies.get('tracker_session','').encode()).hexdigest(),))
    with db() as c:audit(c,u['email'],'Signed out')
    response.delete_cookie('tracker_session',path='/'); return {'ok':True}

class PasswordChange(BaseModel):
    current_password:str=Field(max_length=1024)
    new_password:str=Field(min_length=12,max_length=1024)
@app.post('/api/password')
def change_password(body:PasswordChange,u=Depends(auth)):
    if not verify_password(body.current_password,u['password_hash']): raise HTTPException(400,'Current password is incorrect')
    with db() as c:
        c.execute('UPDATE users SET password_hash=%s WHERE id=%s',(hash_password(body.new_password),u['id']))
        c.execute('DELETE FROM sessions WHERE user_id=%s',(u['id'],)); audit(c,u['email'],'Password changed')
    return {'ok':True}

@app.get('/api/meta')
def meta(u=Depends(auth)):
    with db() as c:
        lists=setting(c,'lists'); people=c.execute('SELECT id,name,email,role,team FROM users WHERE active=true ORDER BY name').fetchall()
        if u['role']=='client':
            lists={k:v for k,v in lists.items() if k in {'Environment','Issue Type','Severity','Priority','Status'}}; lists['Client']=u['clients']; people=[]
        return {'fields':[f for f in FIELDS if u['role']!='client' or f['key'] in CLIENT_FIELDS], 'lists':lists,'sla':setting(c,'sla'),'people':people,'roles':ROLES,'permission_keys':list(BASE['super_admin']),'role_permissions':setting(c,'role_permissions'),'source_file':SEED['source_file']}

@app.get('/api/issues')
def issues(q:str='',status:str='',client:str='',severity:str='',assigned_to:str='',review:bool=False,release:str='',open_closed:str='',sla_status:str='',request_type:str='',u=Depends(auth)):
    with db() as c:
        sla=setting(c,'sla'); releases=release_map(c)
        rows=c.execute('SELECT * FROM issues ORDER BY created_at DESC,id DESC').fetchall()
        result=[]
        for row in rows:
            raw=row['data']
            if not can_read(u,raw):continue
            if request_type and request_kind(raw)!=request_type:continue
            d=calculate(raw,sla,releases); d.update(revision=row['revision'],updated_at=row['updated_at'].isoformat()); d=visible(u,d)
            if q and q.lower() not in ' '.join(str(v) for v in d.values()).lower():continue
            if status and (d.get('status') or 'Unclassified')!=status:continue
            if client and client not in [v.strip() for v in str(d.get('client') or '').split(',')]:continue
            if severity and (d.get('severity') or 'Unclassified')!=severity:continue
            if assigned_to and d.get('assigned_to')!=assigned_to:continue
            if release and d.get('target_fix_release')!=release:continue
            if open_closed and d.get('open_closed')!=open_closed:continue
            if sla_status and d.get('sla_status')!=sla_status:continue
            if review and not d.get('review_flags'):continue
            result.append(d)
        return {'items':result,'total':len(result)}

@app.get('/api/dashboard')
def dashboard(u=Depends(auth)):
    data=issues(u=u)['items']
    from collections import Counter
    opened=[x for x in data if x['open_closed']=='Open']
    return {'request_type_summary':request_summary(data),'total':len(data),'open':len(opened),'closed':len(data)-len(opened),
            'unclassified_status':sum(not x.get('status') for x in data),'needs_review':sum(bool(x.get('review_flags')) for x in data),
            'sla_breached':sum(x['sla_status']=='Breached' for x in opened),'at_risk':sum(x['sla_status']=='At Risk' for x in opened),
            'unassigned':sum(not x.get('assigned_to') for x in opened) if u['role']!='client' else None,
            'severity':dict(Counter(x.get('severity') or 'Unclassified' for x in opened)),
            'status':dict(Counter(x.get('status') or 'Unclassified' for x in data)),
            'clients':dict(Counter(x.get('client') or 'Unassigned client' for x in opened)),
            'owners':dict(Counter(x.get('assigned_to') or 'Unassigned' for x in opened)) if u['role']!='client' else {},
            'recent':data[:7]}

@app.get('/api/issues/{issue_id}')
def detail(issue_id:str,u=Depends(auth)):
    with db() as c:
        issue=visible(u,enrich(c,get_issue(c,issue_id,u)))
        comments=c.execute('SELECT c.id,c.body,c.internal,c.created_at,u.name FROM comments c JOIN users u ON u.id=c.user_id WHERE issue_id=%s AND (%s OR c.internal=false) ORDER BY c.id',(issue_id,u['role']!='client')).fetchall()
        attachments=c.execute('SELECT id,name,size,category,created_at FROM attachments WHERE issue_id=%s ORDER BY created_at',(issue_id,)).fetchall()
        history=c.execute('SELECT actor,action,changes,created_at FROM audit WHERE issue_id=%s ORDER BY id DESC LIMIT 100',(issue_id,)).fetchall() if u['role']!='client' else []
        cycles=c.execute('SELECT w.*,u.name AS developer_name FROM work_cycles w JOIN users u ON u.id=w.developer_id WHERE issue_id=%s ORDER BY w.id DESC',(issue_id,)).fetchall() if u['role']!='client' else []
        events=c.execute('SELECT e.*,u.name AS actor_name FROM issue_events e LEFT JOIN users u ON u.id=e.actor_id WHERE issue_id=%s ORDER BY e.id DESC',(issue_id,)).fetchall() if u['role']!='client' else []
        latest=history[0] if history else None
        return {'issue':issue,'comments':comments,'attachments':attachments,'history':history,'cycles':cycles,'events':events,'latest_action':latest}

class IssueCreate(BaseModel):
    data:dict
@app.post('/api/issues',status_code=201)
def create_issue(body:IssueCreate,u=Depends(auth)):
    require_action(u,'raise')
    with db() as c:
        patch={**body.data}; patch.pop('bug_id',None)
        if any(patch.get(k) not in (None,'') for k in (INTAKE_DEFERRED_FIELDS|(lifecycle.CONTROLLED-{'target_fix_release','post_deploy_action','data_correction_plan','repeat_signature','test_evidence_ref','communication_email_date','current_stage'}))):raise HTTPException(422,'Resolution, QA, actual deployment and closure values must be recorded by the responsible role later in the workflow')
        if patch.get('status') not in (None,'','New'):raise HTTPException(422,'New issues must enter the assignment workflow')
        if patch.get('assigned_to') or patch.get('team'):raise HTTPException(422,'Use named developer and tester assignment controls')
        patch['reported_by']=u['name']
        watcher_ids=patch.pop('watcher_user_ids',[])
        if not isinstance(watcher_ids,list) or any(type(x) is not int for x in watcher_ids):raise HTTPException(422,'Watcher IDs must be a list of user numbers')
        developer_id=patch.pop('developer_user_id',None);tester_id=patch.pop('tester_user_id',None);against_id=patch.pop('reported_against_user_id',None)
        for uid in [developer_id,tester_id,against_id]:
            if uid is not None and (type(uid) is not int or uid<1):raise HTTPException(422,'Assignment IDs must be positive user numbers')
        if u['role']=='client' and any([developer_id,tester_id,against_id,watcher_ids]):raise HTTPException(403,'Clients cannot assign internal workflow participants')
        if u['role']!='client' and not developer_id:raise HTTPException(422,'Select a Product Developer or Process Developer')
        if u['role']=='client':
            allowed={'title','client','client_ticket_ref','environment','steps_to_reproduce','expected_result','actual_result','issue_type','business_justification','acceptance_criteria'}
            patch.pop('reported_by',None)
            if set(patch)-allowed: raise HTTPException(403,'Clients may submit issue details only')
            if patch.get('client') not in u['clients']:raise HTTPException(403,'Choose one of your assigned clients')
            patch.update(reported_by=u['name'],source='Client Reported',date_reported=business_date().isoformat())
        patch.setdefault('date_reported',business_date().isoformat()); patch.setdefault('status','New'); patch.setdefault('reported_by',u['name'])
        patch.setdefault('issue_type','Bug')
        data=validate_patch(patch,{},FIELDS,setting(c,'lists'),release_map(c))
        lifecycle.validate_intake(data,client=u['role']=='client')
        lifecycle.freeze_sla(data,setting(c,'sla'))
        prefix,sequence=PREFIXES[request_kind(data)]
        number=c.execute("SELECT nextval(%s) AS n",(sequence,)).fetchone()['n'];issue_id=f'{prefix}-{number:04d}'
        data['bug_id']=issue_id; data['reopen_count']=0;data['reporter_user_id']=u['id']
        for wid in watcher_ids:
            watcher=workflow.user_by_id(c,wid)
            if not can_read(watcher,data):raise HTTPException(422,'A selected watcher does not have client access to this issue')
        data['watcher_user_ids']=watcher_ids
        data['reported_against_user_id']=int(against_id) if against_id else None
        if against_id and workflow.user_by_id(c,against_id)['role'] not in DEV_ROLES:raise HTTPException(422,'Reported-against user must be a developer')
        c.execute('INSERT INTO issues(id,data) VALUES(%s,%s)',(issue_id,Jsonb(data)))
        if developer_id:
            developer=workflow.user_by_id(c,developer_id)
            tester=workflow.user_by_id(c,tester_id or (u['id'] if developer['role']=='process_developer' and u['role']=='process_designer' else None))
            workflow.begin_cycle(c,data,developer,tester,u)
            c.execute('UPDATE issues SET data=%s WHERE id=%s',(Jsonb(data),issue_id))
        from .notifications import notify_issue
        notify_issue(c,data,'Issue created')
        audit(c,u['email'],'Issue created',issue_id,{'title':data['title']})
        return visible(u,enrich(c,get_issue(c,issue_id,u)))

class IssueUpdate(BaseModel):
    revision:int
    data:dict
@app.patch('/api/issues/{issue_id}')
def update_issue(issue_id:str,body:IssueUpdate,u=Depends(auth)):
    require_action(u,'edit')
    with db() as c:
        old=get_issue(c,issue_id,u,True)
        if old['revision']!=body.revision:raise HTTPException(409,'Another user updated this issue. Reload before saving.')
        patch=dict(body.data)
        protected=lifecycle.CONTROLLED|{'reported_by','status','assigned_to','team','root_cause_summary','resolved_date','closure_date','closed_by','verified_by','qa_verified_date','resolution_type'}
        if protected.intersection(patch):raise HTTPException(422,'Use workflow actions for assignment, fixes, QA and closure')
        if 'status' in patch and patch['status']!=old['data'].get('status'):raise HTTPException(422,'Link this legacy issue to the workflow before changing status')
        if 'bug_id' in patch:raise HTTPException(422,'Issue IDs cannot be changed')
        if 'reopen_count' in patch:raise HTTPException(422,'Reopen count is maintained automatically')
        if 'issue_type' in patch and request_kind(patch)!=request_kind(old['data']):raise HTTPException(422,'Request category cannot change after ID allocation; create a linked request instead')
        data=validate_patch(patch,old['data'],FIELDS,setting(c,'lists'),release_map(c))
        if old['data'].get('workflow_route'):lifecycle.validate_intake(data)
        if data.get('severity')!=old['data'].get('severity'):lifecycle.freeze_sla(data,setting(c,'sla'))
        from .sla_tracking import record_breaches
        record_breaches(c)
        before=old['data'].get('status'); after=data.get('status')
        if before in TERMINAL and after not in TERMINAL and after!='Reopened': raise HTTPException(422,'Use Reopened to reopen a resolved or closed issue')
        if after=='Reopened' and before!='Reopened':
            data['reopen_count']=int(old['data'].get('reopen_count') or 0)+1
            for key in ['resolved_date','closure_date','closed_by']: data[key]=None
        if after=='Resolved' and before!=after and not data.get('resolved_date'):raise HTTPException(422,'Resolution date is required')
        if after=='Closed' and before!=after:
            needed=['resolved_date','resolution_type','verified_by','qa_verified_date','root_cause_summary']
            if data.get('data_correction_required')=='Yes':needed+=['data_correction_completed_on']
            if data.get('source')=='Client Reported' and data.get('client_confirmation')!='Confirmed':raise HTTPException(422,'Client confirmation is required before closure')
            if str(data.get('detection_stage') or '').startswith('Post:') and data.get('severity') in {'S1 - Critical','S2 - High'} and data.get('rca_shared')!='Yes':raise HTTPException(422,'Share the RCA before closing a post-deployment S1/S2 issue')
            missing=[f for f in needed if not data.get(f)]
            if missing:raise HTTPException(422,'Closure requires: '+', '.join(missing))
            data['closed_by']=u['name']; data['closure_date']=business_date().isoformat()
        changes={k:{'from':old['data'].get(k),'to':v} for k,v in data.items() if old['data'].get(k)!=v}
        if changes:
            c.execute('UPDATE issues SET data=%s,revision=revision+1,updated_at=now() WHERE id=%s',(Jsonb(data),issue_id))
            from .notifications import notify_issue
            notify_issue(c,data,'Issue details updated')
            audit(c,u['email'],'Issue updated',issue_id,changes)
        return visible(u,enrich(c,get_issue(c,issue_id,u)))

class CommentBody(BaseModel):
    body:str=Field(min_length=1,max_length=20000)
    internal:bool=False
@app.post('/api/issues/{issue_id}/comments',status_code=201)
def comment(issue_id:str,body:CommentBody,u=Depends(auth)):
    require_action(u,'comment')
    if not body.body.strip():raise HTTPException(422,'Comment cannot be blank')
    if u['role']=='client' and body.internal:raise HTTPException(403,'Clients cannot add internal notes')
    with db() as c:
        issue=get_issue(c,issue_id,u)['data']
        if issue.get('assignee_user_id')==u['id'] and issue.get('developer_user_id')==u['id']:workflow.acknowledge(c,issue,u)
        from .notifications import notify_issue
        notify_issue(c,issue,'Internal note added' if body.internal else 'Comment added',internal=body.internal)
        c.execute('INSERT INTO comments(issue_id,user_id,body,internal) VALUES(%s,%s,%s,%s)',(issue_id,u['id'],body.body.strip(),body.internal))
        audit(c,u['email'],'Internal note added' if body.internal else 'Comment added',issue_id)
    return {'ok':True}

@app.post('/api/issues/{issue_id}/attachments',status_code=201)
async def attach(issue_id:str,file:UploadFile=File(...),u=Depends(auth)):
    require_action(u,'attach')
    content=await file.read(MAX_FILE+1)
    if len(content)>MAX_FILE:raise HTTPException(413,'Maximum attachment size is 20 MB')
    name=Path((file.filename or 'attachment').replace('\\','/')).name[:200]
    with db() as c:
        data=get_issue(c,issue_id,u)['data']; aid=str(uuid.uuid4())
        from .uploads import validate_attachment
        validate_attachment(name,content)
        from .notifications import notify_issue
        notify_issue(c,data,'Supporting attachment added')
        c.execute('INSERT INTO attachments(id,issue_id,user_id,name,content,size,category) VALUES(%s,%s,%s,%s,%s,%s,%s)',(aid,issue_id,u['id'],name,content,len(content),'media' if Path(name).suffix.lower() in {'.png','.jpg','.jpeg','.webp','.gif','.mp4','.webm','.mov'} else 'supporting_document'))
        audit(c,u['email'],'Attachment added',issue_id,{'name':name})
    return {'id':aid,'name':name}

@app.get('/api/attachments/{attachment_id}')
def attachment(attachment_id:uuid.UUID,u=Depends(auth)):
    with db() as c:
        row=c.execute('SELECT * FROM attachments WHERE id=%s',(attachment_id,)).fetchone()
        if not row:raise HTTPException(404,'Attachment not found')
        get_issue(c,row['issue_id'],u)
        from urllib.parse import quote
        return Response(bytes(row['content']),media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row['name'])})

@app.get('/api/releases')
def releases(u=Depends(auth)):
    require(u,{'admin','manager','editor','viewer'})
    with db() as c:
        bugs=issues(u=u)['items']; rows=c.execute('SELECT * FROM releases ORDER BY data->>\'planned_date\',id').fetchall()
        items=[]
        for row in rows:
            planned=[b for b in bugs if b.get('target_fix_release')==row['id']]
            blockers=[b for b in planned if b['open_closed']=='Open' and (b.get('release_blocker')=='Yes' or b.get('severity') in {'S1 - Critical','S2 - High'})]
            items.append({**row['data'],'revision':row['revision'],'planned_fixes':len(planned),'closed_fixes':sum(b['open_closed']=='Closed' for b in planned),'open_blockers':len(blockers),'shipped':sum(b.get('actual_fix_release')==row['id'] for b in bugs)})
        return {'items':items,'template_examples':setting(c,'template_releases')}

class ReleaseBody(BaseModel):
    release_id:str=Field(min_length=1,max_length=80,pattern=r'^[A-Za-z0-9._-]+$')
    version:str=Field(min_length=1,max_length=80)
    type:str
    planned_date:date
    actual_date:date|None=None
    status:str
    notes:str=Field(default='',max_length=20000)
    revision:int|None=None
@app.put('/api/releases/{release_id}')
def save_release(release_id:str,body:ReleaseBody,u=Depends(auth)):
    require_action(u,'manage_releases')
    if body.release_id!=release_id:raise HTTPException(422,'Release ID mismatch')
    with db() as c:
        lists=setting(c,'lists')
        if body.type not in lists['Release Type'] or body.status not in lists['Release Status']:raise HTTPException(422,'Choose a valid release type and status')
        old=c.execute('SELECT * FROM releases WHERE id=%s FOR UPDATE',(release_id,)).fetchone()
        if old and old['revision']!=body.revision:raise HTTPException(409,'Release changed; reload it')
        if body.actual_date and body.actual_date>business_date():raise HTTPException(422,'Actual release date cannot be in the future')
        if body.status=='Released' and not body.actual_date:raise HTTPException(422,'Actual release date is required for a released version')
        if body.status=='Released' and (not old or old['data'].get('status')!='Released'):
            blockers=c.execute("SELECT id FROM issues WHERE data->>'target_fix_release'=%s AND coalesce(data->>'status','') != ALL(%s) AND NOT (data->>'status'=ANY(ARRAY['Ready for Deployment','Ready for Closure']) AND data->>'qa_passed_at' IS NOT NULL) AND (data->>'release_blocker'='Yes' OR data->>'severity'=ANY(%s))",(release_id,list(TERMINAL),['S1 - Critical','S2 - High'])).fetchall()
            if blockers:raise HTTPException(422,'Release is blocked by open issues: '+', '.join(r['id'] for r in blockers))
        data=body.model_dump(mode='json',exclude={'revision'})
        if old:c.execute('UPDATE releases SET data=%s,revision=revision+1,updated_at=now() WHERE id=%s',(Jsonb(data),release_id))
        else:c.execute('INSERT INTO releases(id,data) VALUES(%s,%s)',(release_id,Jsonb(data)))
        audit(c,u['email'],'Release saved',changes={'release_id':release_id,'data':data})
    return {'ok':True}

def safe_csv(value):
    value='' if value is None else str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
@app.get('/api/export/issues.csv')
def export_issues(q:str='',status:str='',client:str='',severity:str='',assigned_to:str='',review:bool=False,release:str='',open_closed:str='',sla_status:str='',request_type:str='',u=Depends(auth)):
    rows=issues(q=q,status=status,client=client,severity=severity,assigned_to=assigned_to,review=review,release=release,open_closed=open_closed,sla_status=sla_status,u=u)['items']
    fields=[f for f in FIELDS if u['role']!='client' or f['key'] in CLIENT_FIELDS]
    buff=io.StringIO();writer=csv.writer(buff);writer.writerow([f['label'] for f in fields])
    for row in rows:writer.writerow([safe_csv(row.get(f['key'])) for f in fields])
    return Response('\ufeff'+buff.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="Reconsyde_Issues.csv"'})

@app.get('/api/comparison')
def comparison(u=Depends(auth)):
    require(u,{'admin','manager','editor','viewer'})
    with db() as c:return setting(c,'comparison')

@app.get('/api/archive')
def archive(u=Depends(auth)):
    require(u,{'admin','manager'})
    with db() as c:return {'source':SEED['source_file'],'sheets':setting(c,'source_archive'),'imports':c.execute('SELECT filename,issue_count,created_at FROM imports ORDER BY created_at').fetchall()}

@app.get('/api/archive/original.xlsx')
def original_workbook(u=Depends(auth)):
    require(u,{'admin','manager'})
    return FileResponse(ROOT/'data/source'/SEED['source_file'],filename=SEED['source_file'],media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.get('/api/audit')
def audit_log(u=Depends(auth)):
    require(u,{'admin','manager'})
    with db() as c:return c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 500').fetchall()

@app.get('/api/settings')
def settings(u=Depends(auth)):
    if u['role']!='manager' and not any(k in u.get('_permissions',effective(u)) for k in ['manage_masters','manage_rights']):raise HTTPException(403,'Configuration access denied')
    with db() as c:return {'lists':setting(c,'lists'),'sla':setting(c,'sla')}

class SettingsBody(BaseModel):
    data:dict|list
@app.put('/api/settings/{key}')
def save_setting(key:str,body:SettingsBody,u=Depends(auth)):
    require_action(u,'manage_masters')
    if key not in {'lists','sla'}:raise HTTPException(404,'Setting not found')
    if key=='lists':
        if not isinstance(body.data,dict):raise HTTPException(422,'Lists must be an object')
        for k,v in body.data.items():
            if not isinstance(k,str) or not isinstance(v,list) or any(not isinstance(s,str) or not s.strip() or len(s)>200 for s in v) or len(set(v))!=len(v):raise HTTPException(422,'Each master must contain unique, non-empty strings')
        if any(x not in body.data.get('Status',[]) for x in ['New','In Progress','In QA','Closed','Reopened','Ready for Deployment','Ready for Closure','Duplicate']):raise HTTPException(422,'Retain the five states used by the enforced workflow')
    else:
        if not isinstance(body.data,list) or len(body.data)!=4:raise HTTPException(422,'Keep all four severity rules')
        if {r.get('severity') for r in body.data if isinstance(r,dict)}!=set(SEED['lists']['Severity']):raise HTTPException(422,'Keep S1–S4 severities unique')
        for r in body.data:
            if type(r.get('resolution_days')) is not int or not 1<=r['resolution_days']<=365 or type(r.get('response_hours')) is not int or not 1<=r['response_hours']<=8760:raise HTTPException(422,'Use positive SLA days (1–365) and response hours (1–8760)')
    with db() as c:
        previous=setting(c,key)
        if key=='lists':
            if set(previous)-set(body.data):raise HTTPException(422,'Master list groups cannot be removed')
        c.execute('UPDATE settings SET data=%s WHERE key=%s',(Jsonb(body.data),key));audit(c,u['email'],'Configuration updated',changes={'setting':key,'before':previous,'after':body.data})
    return {'ok':True}

app.mount('/static',StaticFiles(directory=ROOT/'app/static'),name='static')
@app.get('/')
def index():return FileResponse(ROOT/'app/static/index.html')

from .admin_api import router as admin_router
from .operations_api import router as operations_router
app.include_router(admin_router)
app.include_router(operations_router)



from .notification_api import router as notification_router
app.include_router(notification_router)
