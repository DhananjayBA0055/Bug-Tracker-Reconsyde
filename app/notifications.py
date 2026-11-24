import hashlib,json,os,secrets,smtplib,ssl
from datetime import datetime,timedelta,timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo
import httpx
from cryptography.fernet import Fernet
from psycopg.types.json import Jsonb
from urllib.parse import quote
from .domain import calculate,TERMINAL

def cipher():
    key=os.environ.get('SETTINGS_ENCRYPTION_KEY','')
    if not key:raise ValueError('SETTINGS_ENCRYPTION_KEY is required to save connection secrets')
    return Fernet(key.encode())
def encrypt(value):return cipher().encrypt(value.encode()).decode()
def decrypt(value):return cipher().decrypt(value.encode()).decode() if value else ''
def get_setting(c,k):return c.execute('SELECT data FROM settings WHERE key=%s',(k,)).fetchone()['data']
def recipients(c,data,internal=False):
    ids={data.get(k) for k in ['reporter_user_id','developer_user_id','tester_user_id','assignee_user_id']};ids.update(data.get('watcher_user_ids') or []);ids.update(data.get('participant_user_ids') or []);ids.discard(None)
    people=c.execute('SELECT * FROM users WHERE active=true').fetchall()
    attached=[p for p in people if p['id'] in ids or p['name'] in {data.get('assigned_to'),data.get('process_spoc'),data.get('reported_by')}]
    if internal:attached=[p for p in attached if p['role']!='client']
    to=sorted({p['email'] for p in attached});config=get_setting(c,'mail')
    cc=set(config.get('manager_cc',[]))
    for p in attached:cc.update(p.get('manager_emails') or [])
    # Managers are always CC'd; per-user manager mappings can narrow the normal set.
    if not cc:cc={p['email'] for p in people if p['role']=='manager'}
    return sorted(set(to)-cc),sorted(cc)
def queue(c,key,to,cc,subject,body,metadata=None):
    if not to:return
    row=c.execute('INSERT INTO notification_outbox(dedup_key,recipients,cc,subject,body,policy_metadata) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id',(key,Jsonb(to),Jsonb(cc),subject.replace('\r',' ').replace('\n',' ')[:250],body,Jsonb(metadata or {}))).fetchone()
    return row['id'] if row else None

def notify_issue(c,data,action,internal=False):
    from .notification_delivery import publish,process
    event={'Issue created':'created','Assigned':'assigned','Reassign':'assigned','Assign':'assigned','Issue details updated':'details_update','Comment added':'comment','Internal note added':'internal_note','Supporting attachment added':'attachment','Submit Fix':'fix_submitted','Accept':'closed','Verify':'testing','Return':'testing','Reopen':'reopened'}.get(action,'status_update')
    publish(c,event,data,internal=internal);process(c)

def token(cfg):
    r=httpx.post(f"https://login.microsoftonline.com/{quote(cfg['tenant_id'],safe='')}/oauth2/v2.0/token",data={'client_id':cfg['client_id'],'client_secret':decrypt(cfg.get('secret','')),'scope':'https://graph.microsoft.com/.default','grant_type':'client_credentials'},timeout=25)
    r.raise_for_status();return r.json()['access_token']
def send(cfg,to,cc,subject,body):
    if cfg.get('transport')=='graph':
        headers={'Authorization':'Bearer '+token(cfg)}
        r=httpx.post('https://graph.microsoft.com/v1.0/users/'+quote(cfg['sender'],safe='')+'/sendMail',headers=headers,json={'message':{'subject':subject,'body':{'contentType':'Text','content':body},'toRecipients':[{'emailAddress':{'address':a}} for a in to],'ccRecipients':[{'emailAddress':{'address':a}} for a in cc]},'saveToSentItems':True},timeout=30);r.raise_for_status();return
    msg=EmailMessage();msg['From']=cfg['sender'];msg['To']=', '.join(to)
    if cc:msg['Cc']=', '.join(cc)
    msg['Subject']=subject;msg.set_content(body)
    context=ssl.create_default_context()
    if cfg['transport']=='smtp_ssl':server=smtplib.SMTP_SSL(cfg['host'],int(cfg.get('port',465)),timeout=25,context=context)
    else:
        server=smtplib.SMTP(cfg['host'],int(cfg.get('port',587)),timeout=25);server.ehlo();server.starttls(context=context);server.ehlo()
    with server:
        if cfg.get('username'):server.login(cfg['username'],decrypt(cfg.get('secret','')))
        server.send_message(msg,to_addrs=list(set(to+cc)))

def scheduled(c,now=None):
    from .sla_tracking import record_breaches
    from .notification_delivery import publish,process,tray_reports
    record_breaches(c,now)
    cfg=get_setting(c,'mail')
    if not cfg.get('enabled'):return
    now=now or datetime.now(timezone.utc);local=now.astimezone(ZoneInfo(cfg.get('timezone','Asia/Kolkata')))
    sla=get_setting(c,'sla');rels={r['id']:r['data'] for r in c.execute('SELECT * FROM releases').fetchall()}
    trays={}
    for row in c.execute('SELECT * FROM issues').fetchall():
        data=row['data'];d=calculate(data,sla,rels,local.date())
        if d['status'] in TERMINAL:continue
        to,cc=recipients(c,d)
        if d['sla_status']=='Breached':publish(c,'sla_resolution',d,event_key=f"resolution:{row['id']}:{d['due_date']}:{d.get('assigned_at','legacy')}",now=now)
        if data.get('assignee_user_id'):trays.setdefault(data['assignee_user_id'],[]).append(d)
        elif data.get('assigned_to'):
            owner=c.execute('SELECT id FROM users WHERE name=%s AND active=true',(data['assigned_to'],)).fetchall()
            if len(owner)==1:trays.setdefault(owner[0]['id'],[]).append(d)
        rule=data.get('sla_snapshot') or next((s for s in sla if s['severity']==d.get('severity')),None)
        if rule:
            cycle=c.execute('SELECT * FROM work_cycles WHERE issue_id=%s ORDER BY id DESC LIMIT 1',(row['id'],)).fetchone()
            if cycle and not cycle['responded_at'] and now>(cycle.get('response_due_at') or cycle['assigned_at']+timedelta(hours=rule['response_hours'])):
                publish(c,'sla_response',d,event_key=f"response:{cycle['id']}",now=now)
    tray_reports(c,trays,now);process(c,now)


def run_once(db):
    # One scheduler produces deduplicated jobs; delivery uses leased rows and retries.
    with db() as c:
        if c.execute('SELECT pg_try_advisory_xact_lock(934931) AS ok').fetchone()['ok']:scheduled(c)
    for _ in range(30):
        with db() as c:
            cfg=get_setting(c,'mail')
            if not cfg.get('enabled'):return
            row=c.execute("SELECT * FROM notification_outbox WHERE (status IN ('queued','retry') OR status='sending') AND next_attempt<=now() ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
            if not row:return
            c.execute("UPDATE notification_outbox SET status='sending',attempts=attempts+1,next_attempt=now()+interval '5 minutes' WHERE id=%s",(row['id'],))
        try:
            metadata=row.get('policy_metadata') or {}
            if metadata.get('origin')=='notification_centre':
                from .notification_policy import get_policy,effective_rule
                from .main import can_read
                with db() as c:
                    current=get_policy(c)
                    person=c.execute('SELECT * FROM users WHERE id=%s AND active=true',(metadata['recipient_id'],)).fetchone()
                    events=c.execute('SELECT * FROM notification_events WHERE id=ANY(%s)',(metadata['event_ids'],)).fetchall()
                    authorised=bool(person)
                    reschedule=current['revision']!=metadata['policy_revision'] or bool(person and row['recipients']!=[person['email']])
                    latest_cc=set(cfg.get('manager_cc',[]))|set(person.get('manager_emails') or [] if person else [])
                    for event in events:
                        issue=c.execute('SELECT data FROM issues WHERE id=%s',(event['issue_id'],)).fetchone() if event['issue_id'] else None
                        if not person or event['internal'] and person['role']=='client' or issue and not can_read(person,issue['data']):authorised=False;break
                        _,cc=recipients(c,issue['data'] if issue else {'watcher_user_ids':[person['id']]},event['internal']);latest_cc.update(cc)
                        frequency=effective_rule(current,person,event['event_type'])['frequency']
                        if frequency!=metadata['frequency']:reschedule=True
                    row['cc']=sorted(latest_cc)
                    if not authorised or reschedule:
                        c.execute("UPDATE notification_outbox SET status='cancelled' WHERE id=%s",(row['id'],))
                        c.execute("UPDATE notification_deliveries SET status=%s,outbox_id=NULL WHERE outbox_id=%s",('pending' if authorised else 'suppressed',row['id']));continue
            if not row['cc']:raise ValueError('Manager CC is required')
            send(cfg,row['recipients'],row['cc'],row['subject'],row['body'])
            with db() as c:c.execute("UPDATE notification_outbox SET status='sent',sent_at=now(),last_error=NULL WHERE id=%s",(row['id'],))
        except Exception as exc:
            # Keep provider bodies and credentials out of error records.
            error=type(exc).__name__
            with db() as c:c.execute("UPDATE notification_outbox SET status=%s,last_error=%s,next_attempt=now()+%s WHERE id=%s",('dead' if row['attempts']>=5 else 'retry',error,timedelta(minutes=min(60,2**min(row['attempts'],6))),row['id']))
