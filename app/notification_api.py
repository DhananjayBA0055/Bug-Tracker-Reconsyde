from copy import deepcopy
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from psycopg.types.json import Jsonb
from . import main as m,notification_policy as policy

router=APIRouter(prefix='/api/notification-centre')

def can_view(u):
    if not set(policy.PERMISSIONS)&set(u.get('_permissions',m.effective(u))):raise HTTPException(403,'Notification administration access denied')

def people(c):return c.execute('SELECT id,name,email,role,team,active FROM users ORDER BY name').fetchall()

@router.get('')
def settings(u=Depends(m.auth)):
    can_view(u)
    with m.db() as c:
        cfg=m.setting(c,'mail');data=policy.get_policy(c)
        return {'roles':m.ROLES,'teams':['Process Team','Product Team','QA Team'],'template_defaults':policy.defaults()['templates'],'policy':data,'events':policy.EVENTS,'tokens':policy.TOKENS,'people':people(c),'schedule':policy.schedule_config(data,cfg),'mail_enabled':bool(cfg.get('enabled')),'counts':{r['status']:r['count'] for r in c.execute('SELECT status,count(*) FROM notification_deliveries GROUP BY status').fetchall()},'permissions':{key:key in u.get('_permissions',m.effective(u)) for key in policy.PERMISSIONS+['manage_integrations']}}

class PolicyUpdate(BaseModel):
    revision:int
    policy:dict

@router.put('')
def update(body:PolicyUpdate,u=Depends(m.auth)):
    can_view(u)
    with m.db() as c:
        c.execute("SELECT data FROM settings WHERE key='notification_policy' FOR UPDATE")
        old=policy.get_policy(c)
        if body.revision!=old['revision']:raise HTTPException(409,'Notification settings changed; reload before saving')
        data=deepcopy(body.policy)
        try:policy.validate(data,people(c))
        except HTTPException:raise
        except (TypeError,KeyError,AttributeError,ValueError):raise HTTPException(422,'Invalid notification settings structure')
        rights=u.get('_permissions',m.effective(u))
        for key,required in [('templates','edit_notification_templates'),('users','manage_notification_overrides')]:
            if data[key]!=old[key] and required not in rights:raise HTTPException(403,'This change needs '+required)
        if any(data[key]!=old[key] for key in ['defaults','groups','timezone','daily_time','weekly_time','weekly_day']) and 'manage_notifications' not in rights:raise HTTPException(403,'This change needs manage_notifications')
        data['revision']=old['revision']+1
        c.execute("UPDATE settings SET data=%s WHERE key='notification_policy'",(Jsonb(data),))
        # Pending mail is rebuilt with current rules/templates; in-flight/provider-accepted mail cannot be recalled.
        cancelled=c.execute("UPDATE notification_outbox SET status='cancelled' WHERE policy_metadata->>'origin'='notification_centre' AND status IN ('queued','retry') RETURNING id").fetchall()
        if cancelled:c.execute("UPDATE notification_deliveries SET status='pending',outbox_id=NULL WHERE outbox_id=ANY(%s)",([r['id'] for r in cancelled],))
        m.audit(c,u['email'],'Notification settings updated',changes={'revision':data['revision'],'changed_sections':[k for k in data if data[k]!=old.get(k)],'policy':{k:data[k] for k in data if k!='revision' and data[k]!=old.get(k)}})
        return {'policy':data,'message':'Saved. Pending notifications will use these rules. Already sent or in-flight messages cannot be recalled.'}

class Preview(BaseModel):
    user_id:int
    event_type:str
    policy:dict|None=None
    template_key:str|None=None

@router.post('/preview')
def preview(body:Preview,u=Depends(m.auth)):
    can_view(u)
    with m.db() as c:
        users=people(c);person=next((p for p in users if p['id']==body.user_id),None)
        if not person:raise HTTPException(422,'Select a user')
        data=body.policy or policy.get_policy(c)
        try:policy.validate(data,users)
        except HTTPException:raise
        except (TypeError,KeyError,AttributeError,ValueError):raise HTTPException(422,'Invalid notification settings structure')
        if body.event_type not in policy.EVENTS:raise HTTPException(422,'Choose an event')
        key=body.template_key or body.event_type
        if key not in data['templates']:raise HTTPException(422,'Choose an email template')
        rule=policy.effective_rule(data,person,body.event_type);mail=m.setting(c,'mail');now=datetime.now(timezone.utc)
        context={'recipient_name':person['name'],'issue_id':'BUG-0123','title':'Sample reference-format issue','request_type':'Bug','client':'Example Bank','status':'In QA','assignee':'Sample Quality Analyst','event_name':policy.EVENTS[body.event_type],'occurred_at':now.isoformat(),'app_url':mail.get('app_url') or 'https://delivery.example.com','items':'BUG-0123 | Sample reference-format issue | In QA\nREQ-0004 | Sample export enhancement | In Progress','item_count':2,'period':now.date().isoformat()}
        rendered=policy.render(data['templates'][key],context)
        cc=set(mail.get('manager_cc',[]))|set(c.execute('SELECT manager_emails FROM users WHERE id=%s',(person['id'],)).fetchone()['manager_emails'] or [])
        if not cc:cc={p['email'] for p in users if p['role']=='manager' and p['active']}
        return {**rendered,'effective_rule':rule,'next_delivery':policy.next_due(rule['frequency'],now,data,mail).isoformat() if rule['frequency']!='off' else None,'manager_cc':sorted(cc),'mail_enabled':bool(mail.get('enabled')),'sample':True}
