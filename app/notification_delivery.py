"""Durable notification routing and digest dispatch. No provider calls are made here."""
from datetime import datetime,timedelta,timezone,time
from zoneinfo import ZoneInfo
import hashlib,secrets
from psycopg.types.json import Jsonb
from . import notification_policy as policy
from .request_types import kind


def publish(c,event_type,data,event_key=None,internal=False,targets=None,extra=None,now=None,slot=None):
    from .notifications import get_setting,recipients
    mail=get_setting(c,'mail')
    if not mail.get('enabled'):return
    now=now or datetime.now(timezone.utc);settings=policy.get_policy(c)
    to,_=recipients(c,data,internal)
    people=c.execute('SELECT * FROM users WHERE active=true').fetchall()
    if targets is None:people=[p for p in people if p['email'] in to]
    else:people=[p for p in people if p['id'] in targets]
    context={'issue_id':data.get('bug_id',''),'title':data.get('title',''),'request_type':kind(data),'client':data.get('client',''),'status':data.get('status') or 'Unclassified','assignee':data.get('assigned_to') or 'Unassigned','event_name':policy.EVENTS[event_type],'occurred_at':now.isoformat(),'app_url':mail.get('app_url','').rstrip('/'),**(extra or {})}
    if slot:context['_slot']=slot.isoformat()
    row=c.execute('INSERT INTO notification_events(event_key,event_type,issue_id,context,internal,created_at) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id',(event_key or secrets.token_hex(24),event_type,data.get('bug_id'),Jsonb(context),internal,now)).fetchone()
    if not row:return
    from .main import can_read
    for person in people:
        if internal and person['role']=='client' or data.get('bug_id') and not can_read(person,data):continue
        rule=policy.effective_rule(settings,person,event_type);frequency=rule['frequency']
        if frequency=='off':continue
        due=slot or policy.next_due(frequency,now,settings,mail)
        c.execute('INSERT INTO notification_deliveries(event_id,user_id,frequency,due_at) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',(row['id'],person['id'],frequency,due))
    return row['id']


def process(c,now=None):
    from .notifications import get_setting,queue,recipients
    from .main import can_read
    now=now or datetime.now(timezone.utc);mail=get_setting(c,'mail')
    if not mail.get('enabled'):return
    settings=policy.get_policy(c)
    pending=c.execute("SELECT d.*,e.event_type,e.issue_id,e.context,e.internal,e.created_at FROM notification_deliveries d JOIN notification_events e ON e.id=d.event_id WHERE d.status='pending' ORDER BY d.due_at,e.id FOR UPDATE OF d SKIP LOCKED LIMIT 500").fetchall()
    groups={}
    for row in pending:
        person=c.execute('SELECT * FROM users WHERE id=%s AND active=true',(row['user_id'],)).fetchone()
        issue=c.execute('SELECT data FROM issues WHERE id=%s',(row['issue_id'],)).fetchone() if row['issue_id'] else None
        if not person or row['internal'] and person['role']=='client' or issue and not can_read(person,issue['data']):
            c.execute("UPDATE notification_deliveries SET status='suppressed' WHERE event_id=%s AND user_id=%s",(row['event_id'],row['user_id']));continue
        rule=policy.effective_rule(settings,person,row['event_type']);frequency=rule['frequency']
        if frequency=='off':
            c.execute("UPDATE notification_deliveries SET status='suppressed' WHERE event_id=%s AND user_id=%s",(row['event_id'],row['user_id']));continue
        due=datetime.fromisoformat(row['context']['_slot']) if row['event_type']=='tray_report' and row['context'].get('_slot') else policy.next_due(frequency,row['created_at'],settings,mail)
        c.execute('UPDATE notification_deliveries SET frequency=%s,due_at=%s WHERE event_id=%s AND user_id=%s',(frequency,due,row['event_id'],row['user_id']))
        if due>now:continue
        _,cc=recipients(c,issue['data'] if issue else {'watcher_user_ids':[person['id']]},row['internal'])
        cc=sorted(set(cc)|set(person.get('manager_emails') or []))
        group_key=(person['id'],frequency,due.isoformat() if frequency!='immediate' and row['event_type']!='tray_report' else str(row['event_id']))
        groups.setdefault(group_key,{'person':person,'rows':[],'cc':set(),'due':due,'frequency':frequency})
        groups[group_key]['rows'].append(row);groups[group_key]['cc'].update(cc)
    for group in groups.values():
        rows=group['rows'];person=group['person'];first=rows[0];frequency=group['frequency'];cfg=policy.schedule_config(settings,mail)
        template_key=first['event_type'] if frequency=='immediate' or first['event_type']=='tray_report' else frequency+'_digest'
        lines=[f"{r['context'].get('issue_id')} | {r['context'].get('event_name')} | {str(r['context'].get('title',''))[:180]} | {r['context'].get('status')} | {r['context'].get('occurred_at')}" for r in rows]
        context={**first['context'],'recipient_name':person['name'],'period':group['due'].astimezone(ZoneInfo(cfg['timezone'])).date().isoformat(),'items':'\n'.join(lines),'item_count':len(rows)}
        if first['event_type']=='tray_report':context.update(items=first['context'].get('items',''),item_count=first['context'].get('item_count',0))
        rendered=policy.render(settings['templates'][template_key],context)
        fingerprint=hashlib.sha256(','.join(str(r['event_id']) for r in rows).encode()).hexdigest()
        key=f"centre:{person['id']}:{frequency}:{settings['revision']}:{fingerprint}"
        outbox=queue(c,key,[person['email']],sorted(group['cc']),rendered['subject'],rendered['body'],{'origin':'notification_centre','policy_revision':settings['revision'],'recipient_id':person['id'],'event_ids':[r['event_id'] for r in rows],'frequency':frequency,'template':template_key})
        if outbox:
            for row in rows:c.execute("UPDATE notification_deliveries SET status='queued',outbox_id=%s WHERE event_id=%s AND user_id=%s",(outbox,row['event_id'],person['id']))


def tray_reports(c,trays,now):
    from .notifications import get_setting
    mail=get_setting(c,'mail');settings=policy.get_policy(c);cfg=policy.schedule_config(settings,mail);local=now.astimezone(ZoneInfo(cfg['timezone']))
    for uid,items in trays.items():
        person=c.execute('SELECT * FROM users WHERE id=%s AND active=true',(uid,)).fetchone()
        if not person:continue
        rule=policy.effective_rule(settings,person,'tray_report');frequency=rule['frequency']
        if frequency=='off':continue
        clock=time.fromisoformat(cfg['daily_time'] if frequency=='daily' else cfg['weekly_time'])
        slot=datetime.combine(local.date(),clock,tzinfo=local.tzinfo)
        if local<slot or frequency=='weekly' and local.weekday()!=cfg['weekly_day']:continue
        lines=[f"{d['bug_id']} | {d.get('issue_type') or 'Bug'} | {str(d.get('title',''))[:180]} | {d.get('status') or 'Unclassified'} | SLA: {d.get('sla_status')}" for d in items]
        publish(c,'tray_report',{},event_key=f"tray:{uid}:{frequency}:{slot.date()}",targets=[uid],extra={'items':'\n'.join(lines),'item_count':len(items)},now=now,slot=slot)
