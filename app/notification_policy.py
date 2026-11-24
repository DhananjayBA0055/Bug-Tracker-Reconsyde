"""Notification preferences, deterministic scope inheritance and safe text templates."""
from copy import deepcopy
from datetime import datetime,timedelta,time,timezone
from zoneinfo import ZoneInfo
import re
from fastapi import HTTPException
from .permissions import ROLES,TEAMS

EVENTS={'created':'New bug / request','assigned':'Assignment / reassignment','status_update':'Status / milestone update','details_update':'Reporting details changed','comment':'Shared discussion','internal_note':'Internal note','attachment':'Attachment uploaded','fix_submitted':'Rectification submitted','testing':'Testing / return for correction','closed':'Closure','reopened':'Reopened','sla_response':'Response SLA breach','sla_resolution':'Resolution SLA breach','tray_report':'Open-tray report'}
FREQUENCIES=['immediate','daily','weekly','off']
TOKENS=['recipient_name','issue_id','title','request_type','client','status','assignee','event_name','occurred_at','app_url','items','item_count','period']
PATTERN=re.compile(r'{{\s*([a-z_]+)\s*}}')
PERMISSIONS=['manage_notifications','edit_notification_templates','manage_notification_overrides']

def defaults():
    templates={k:{'subject':'[Bancapp] {{issue_id}} — {{event_name}}','body':'Hello {{recipient_name}},\n\n{{event_name}}\n\nRequest: {{issue_id}}\nType: {{request_type}}\nTitle: {{title}}\nClient: {{client}}\nStatus: {{status}}\nCurrent tray: {{assignee}}\nUpdated: {{occurred_at}}\n\nOpen Delivery Desk: {{app_url}}\n\nBancapp Automation'} for k in EVENTS}
    templates['sla_response']['subject']='[Bancapp SLA] {{issue_id}} response overdue'
    templates['sla_resolution']['subject']='[Bancapp SLA] {{issue_id}} resolution overdue'
    templates['tray_report']={'subject':'[Bancapp] Day-end open request report — {{period}}','body':'Hello {{recipient_name}},\n\n{{item_count}} open requests are in your tray:\n\n{{items}}\n\nOpen Delivery Desk: {{app_url}}\n\nBancapp Automation'}
    for k in ['daily_digest','weekly_digest']:templates[k]={'subject':'[Bancapp] '+k.replace('_',' ').title()+' — {{period}}','body':'Hello {{recipient_name}},\n\n{{item_count}} updates in this {{period}} notification summary:\n\n{{items}}\n\nOpen Delivery Desk: {{app_url}}\n\nBancapp Automation'}
    return {'revision':1,'timezone':None,'daily_time':None,'weekly_day':4,'weekly_time':None,'defaults':{k:{'enabled':True,'frequency':'daily' if k=='tray_report' else 'immediate','locked':False} for k in EVENTS},'groups':[],'users':{},'templates':templates}

def get_policy(c):
    row=c.execute("SELECT data FROM settings WHERE key='notification_policy'").fetchone()
    return row['data'] if row else defaults()

def scopes(policy,user):
    groups=[g for g in policy['groups'] if (g['scope']=='role' and g.get('value')==user['role']) or (g['scope']=='team' and g.get('value')==user.get('team')) or (g['scope']=='custom' and user['id'] in g.get('members',[]))]
    return sorted(groups,key=lambda g:({'role':0,'team':1,'custom':2}[g['scope']],g.get('priority',0),g['id']))

def effective_rule(policy,user,event):
    if user.get('active') is False:return {'enabled':False,'frequency':'off','source':'Inactive account','locked':True}
    if event=='internal_note' and user['role']=='client':return {'enabled':False,'frequency':'off','source':'Client accounts cannot receive internal notes','locked':True}
    rule=deepcopy(policy['defaults'][event]);source='Workspace default';locked=rule.get('locked',False)
    for g in scopes(policy,user):
        patch=g.get('rules',{}).get(event)
        if patch and not locked:rule.update(patch);source=g['name'];locked=rule.get('locked',False)
    patch=policy.get('users',{}).get(str(user['id']),{}).get('rules',{}).get(event)
    if patch and not locked:rule.update(patch);source='Individual override'
    if not rule.get('enabled'):rule['frequency']='off'
    return {**rule,'source':source,'locked':locked}

def validate(policy,people):
    allowed={'revision','timezone','daily_time','weekly_time','weekly_day','defaults','groups','users','templates'}
    if not isinstance(policy,dict) or set(policy)!=allowed:raise HTTPException(422,'Use the complete notification settings structure')
    if type(policy.get('revision')) is not int or policy['revision']<1:raise HTTPException(422,'Invalid policy revision')
    if not isinstance(policy.get('groups'),list) or not isinstance(policy.get('users'),dict) or not isinstance(policy.get('templates'),dict) or not isinstance(policy.get('defaults'),dict):raise HTTPException(422,'Invalid rule, group or template structure')
    if policy['timezone']:
        try:ZoneInfo(policy['timezone'])
        except Exception:raise HTTPException(422,'Choose a valid timezone')
    for key in ['daily_time','weekly_time']:
        if policy[key] is not None:
            try:time.fromisoformat(policy[key])
            except (ValueError,TypeError):raise HTTPException(422,'Use HH:MM schedule times')
            if not re.fullmatch(r'\d{2}:\d{2}',policy[key]):raise HTTPException(422,'Use HH:MM schedule times')
    if type(policy['weekly_day']) is not int or policy['weekly_day'] not in range(7):raise HTTPException(422,'Choose a weekday')
    if set(policy['defaults'])!=set(EVENTS):raise HTTPException(422,'Keep every notification event')
    def rules(data,full=False):
        if set(data)-set(EVENTS):raise HTTPException(422,'Unknown notification event')
        for event,rule in data.items():
            if not isinstance(rule,dict) or set(rule)-{'enabled','frequency','locked'}:raise HTTPException(422,'Invalid notification rule')
            if full and set(rule)!={'enabled','frequency','locked'}:raise HTTPException(422,'Complete each default rule')
            if any(key in rule and type(rule[key]) is not bool for key in ['enabled','locked']):raise HTTPException(422,'Enabled and mandatory must be boolean')
            if 'frequency' in rule and rule['frequency'] not in FREQUENCIES:raise HTTPException(422,'Choose immediate, daily, weekly or off')
            if event=='tray_report' and rule.get('frequency')=='immediate':raise HTTPException(422,'Open-tray reports support daily, weekly or off')
    rules(policy['defaults'],True)
    ids={p['id'] for p in people};seen=set()
    if len(policy['groups'])>100:raise HTTPException(422,'Maximum 100 notification groups')
    for g in policy['groups']:
        if set(g)-{'id','name','scope','value','members','priority','rules'} or not g.get('id') or g['id'] in seen or not 1<=len(str(g.get('name','')).strip())<=100:raise HTTPException(422,'Groups need unique IDs and names')
        seen.add(g['id'])
        if g['scope'] not in {'role','team','custom'}:raise HTTPException(422,'Choose role, team or custom group')
        if g['scope']=='role' and g.get('value') not in ROLES:raise HTTPException(422,'Unknown group role')
        if g['scope']=='team' and g.get('value') not in TEAMS:raise HTTPException(422,'Unknown team')
        if any(type(uid) is not int or uid not in ids for uid in g.get('members',[])):raise HTTPException(422,'Select existing group members')
        if type(g.get('priority',0)) is not int:raise HTTPException(422,'Group priority must be an integer')
        rules(g.get('rules',{}))
    for uid,settings in policy['users'].items():
        if not str(uid).isdigit() or int(uid) not in ids or set(settings)!={'rules'}:raise HTTPException(422,'Invalid individual notification override')
        rules(settings['rules'])
    if set(policy['templates'])!=set(EVENTS)|{'daily_digest','weekly_digest'}:raise HTTPException(422,'Keep every event and digest template')
    for template in policy['templates'].values():
        if set(template)!={'subject','body'} or any(not isinstance(template[k],str) or not template[k].strip() for k in ['subject','body']):raise HTTPException(422,'Each email needs a subject and body')
        if len(template['subject'])>250 or '\r' in template['subject'] or '\n' in template['subject'] or len(template['body'])>20000:raise HTTPException(422,'Subject maximum 250 characters on one line; body maximum 20,000')
        for text in template.values():
            if set(PATTERN.findall(text))-set(TOKENS):raise HTTPException(422,'Unknown template placeholders')
            if '{{' in PATTERN.sub('',text) or '}}' in PATTERN.sub('',text):raise HTTPException(422,'Use {{placeholder}} syntax')
    return policy

def render(template,context):
    return {key:PATTERN.sub(lambda m:str(context.get(m.group(1),'') or ''),template[key]) for key in ['subject','body']}

def schedule_config(policy,mail):
    return {'timezone':policy.get('timezone') or mail.get('timezone','Asia/Kolkata'),'daily_time':policy.get('daily_time') or f"{int(mail.get('day_end_hour',18)):02d}:{int(mail.get('day_end_minute',0)):02d}",'weekly_time':policy.get('weekly_time') or policy.get('daily_time') or f"{int(mail.get('day_end_hour',18)):02d}:{int(mail.get('day_end_minute',0)):02d}",'weekly_day':policy['weekly_day']}

def next_due(frequency,occurred,policy,mail):
    if frequency=='immediate':return occurred
    cfg=schedule_config(policy,mail);local=occurred.astimezone(ZoneInfo(cfg['timezone']))
    clock=time.fromisoformat(cfg['daily_time'] if frequency=='daily' else cfg['weekly_time'])
    due=datetime.combine(local.date(),clock,tzinfo=local.tzinfo)
    if frequency=='daily':
        if due<local:due+=timedelta(days=1)
    else:
        due+=timedelta(days=(cfg['weekly_day']-due.weekday())%7)
        if due<local:due+=timedelta(days=7)
    return due.astimezone(timezone.utc)
