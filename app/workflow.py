from .clock import business_date
from datetime import datetime,timezone,timedelta
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from .permissions import DEV_ROLES,ADMIN_ROLES
from . import lifecycle

def user_by_id(c,uid):
    if not uid:raise HTTPException(422,'Select a named user for this assignment')
    u=c.execute('SELECT * FROM users WHERE id=%s AND active=true',(int(uid),)).fetchone()
    if not u:raise HTTPException(422,'Selected user is missing or disabled')
    return u

def routing(developer,tester):
    if developer['role'] not in DEV_ROLES:raise HTTPException(422,'Assign work to a Product Developer or Process Developer')
    route='product' if developer['role']=='product_developer' else 'process'
    role='quality_analyst' if route=='product' else 'process_designer'
    if tester['role']!=role:raise HTTPException(422,'Product work must return to QA; process work must return to a Process Designer')
    return route

def begin_cycle(c,data,developer,tester,actor,now=None):
    now=now or datetime.now(timezone.utc)
    route=routing(developer,tester)
    data['participant_user_ids']=sorted(set(data.get('participant_user_ids') or [])|{developer['id'],tester['id'],actor['id']}|{x for x in [data.get('developer_user_id'),data.get('tester_user_id'),data.get('reporter_user_id')] if x})
    if developer['id']==tester['id']:raise HTTPException(422,'Developer and tester must be different people')
    data.pop('qa_passed_at',None);data.pop('deployed_at',None)
    for key in ['qa_test_evidence','regression_test_result','client_confirmation','client_confirmation_ref','rca_shared','rca_shared_ref']:data.pop(key,None)
    for key in ['actual_fix_release','deployment_evidence','client_production_deployment_date','data_correction_completed_on','developer_test_evidence','regression_test_ref','code_ref','deployment_ticket_ref','verification_steps','prevention_action','root_cause_category','root_cause_summary','duplicate_of_issue_id']:data.pop(key,None)
    data.pop('developer_resolution',None);data.pop('developer_rca',None);data.pop('resolution_author_id',None)
    data.update(bucket=route,workflow_route=route,developer_user_id=developer['id'],tester_user_id=tester['id'],assignee_user_id=developer['id'],
                assigned_to=developer['name'],team=developer['team'],status='In Progress',assigned_at=now.isoformat(),
                resolution_type=None,resolved_date=None,closure_date=None,closed_by=None,verified_by=None,qa_verified_date=None)
    rule=data.get('sla_snapshot') or {}
    due=now+timedelta(hours=int(rule['response_hours'])) if rule.get('response_hours') else None
    c.execute('INSERT INTO work_cycles(issue_id,developer_id,assigned_at,response_due_at) VALUES(%s,%s,%s,%s)',(data['bug_id'],developer['id'],now,due))
    event(c,data['bug_id'],actor,'assigned',{'developer_id':developer['id'],'tester_id':tester['id'],'route':route})
    return data

def event(c,issue_id,actor,kind,data=None):
    c.execute('INSERT INTO issue_events(issue_id,actor_id,kind,data) VALUES(%s,%s,%s,%s)',(issue_id,actor['id'],kind,Jsonb(data or {})))

def acknowledge(c,data,actor,now=None):
    if data.get('assignee_user_id')!=actor['id'] or data.get('developer_user_id')!=actor['id']:raise HTTPException(403,'Only the developer holding the issue may acknowledge it')
    now=now or datetime.now(timezone.utc)
    c.execute('UPDATE work_cycles SET responded_at=coalesce(responded_at,%s) WHERE id=(SELECT max(id) FROM work_cycles WHERE issue_id=%s AND fixed_at IS NULL)',(now,data['bug_id']))
    event(c,data['bug_id'],actor,'acknowledged')

def submit_fix(c,data,actor,resolution,rca,now=None):
    if actor['role'] not in DEV_ROLES or data.get('assignee_user_id')!=actor['id'] or data.get('developer_user_id')!=actor['id']:raise HTTPException(403,'Only the assigned developer can submit this fix')
    if not str(resolution or '').strip() or not str(rca or '').strip():raise HTTPException(422,'Developer resolution and RCA are both mandatory')
    if len(resolution)>20000 or len(rca)>20000:raise HTTPException(422,'Resolution and RCA must each be under 20,000 characters')
    if data.get('status')!='In Progress':raise HTTPException(422,'Only an active developer correction cycle can be submitted')
    now=now or datetime.now(timezone.utc);tester=user_by_id(c,data.get('tester_user_id'))
    routing(actor,tester)
    c.execute('UPDATE work_cycles SET responded_at=coalesce(responded_at,%s),fixed_at=%s,resolution=%s,rca=%s WHERE id=(SELECT max(id) FROM work_cycles WHERE issue_id=%s AND fixed_at IS NULL)',(now,now,resolution,rca,data['bug_id']))
    data.update(developer_resolution=resolution.strip(),developer_rca=rca.strip(),resolution_author_id=actor['id'],
                root_cause_summary='RCA: '+rca.strip()+'\nResolution: '+resolution.strip(),status='In QA',assignee_user_id=tester['id'],assigned_to=tester['name'],team=tester['team'],fixed_at=now.isoformat())
    event(c,data['bug_id'],actor,'fix_submitted',{'tester_id':tester['id'],'fix_record':{key:data.get(key) for key in lifecycle.FIX_FIELDS}})
    return data

def validate_tester(data,actor):
    required='quality_analyst' if data.get('workflow_route')=='product' else 'process_designer'
    if actor['role']!=required or data.get('tester_user_id')!=actor['id'] or data.get('assignee_user_id')!=actor['id']:
        raise HTTPException(403,'Only the designated QA tester or Process Designer for this route can accept or return the fix')
    if data.get('status') not in {'In QA','Ready for Closure','Closed','Duplicate'}:raise HTTPException(422,'The fix must be submitted for testing first')

def accept_fix(c,data,actor,note,now=None):
    validate_tester(data,actor)
    if data.get('status') in {'Closed','Duplicate'}:raise HTTPException(422,'Issue is already closed')
    if not data.get('developer_resolution') or not data.get('developer_rca') or not data.get('resolution_author_id'):raise HTTPException(422,'A developer-authored resolution and RCA are required')
    if not str(note or '').strip():raise HTTPException(422,'Record your test result before closure')
    if data.get('data_correction_required')=='Yes' and not data.get('data_correction_completed_on'):raise HTTPException(422,'Complete the required data correction first')
    now=now or datetime.now(timezone.utc)
    lifecycle.validate_testing(data,note);lifecycle.validate_closure(data)
    data.update(status=lifecycle.close_status(data),resolved_date=business_date(now).isoformat(),closure_date=business_date(now).isoformat(),closed_by=actor['name'],
                verified_by=actor['name'],qa_verified_date=business_date(now).isoformat(),closure_remarks=note.strip(),closed_at=now.isoformat())
    event(c,data['bug_id'],actor,'closed',{'test_result':note.strip()})
    return data

def return_fix(c,data,actor,note,now=None):
    validate_tester(data,actor)
    if not str(note or '').strip():raise HTTPException(422,'Record why the fix is being returned')
    now=now or datetime.now(timezone.utc)
    c.execute('UPDATE work_cycles SET returned_at=%s WHERE id=(SELECT max(id) FROM work_cycles WHERE issue_id=%s)',(now,data['bug_id']))
    data['return_count']=int(data.get('return_count') or 0)+1
    if data.get('status') in {'Closed','Duplicate'}:data['reopen_count']=int(data.get('reopen_count') or 0)+1
    event(c,data['bug_id'],actor,'returned',{'reason':note.strip()})
    return begin_cycle(c,data,user_by_id(c,data['developer_user_id']),user_by_id(c,data['tester_user_id']),actor,now)

def sync_knowledge(c,data):
    valid=data.get('status')=='Closed' and data.get('developer_resolution') and data.get('developer_rca') and data.get('resolution_author_id')
    if not valid:
        c.execute('UPDATE knowledge_articles SET active=false WHERE issue_id=%s',(data['bug_id'],));return
    article={k:data.get(k) for k in ['bug_id','issue_type','title','client','product_module','bug_category','issue_type','environment','developer_resolution','developer_rca','resolution_author_id','verified_by','closure_date','repeat_signature','verification_steps','prevention_action','regression_test_ref','resolution_type','root_cause_category']}
    c.execute("INSERT INTO knowledge_articles(issue_id,data) VALUES(%s,%s) ON CONFLICT(issue_id) DO UPDATE SET data=excluded.data,active=true,visibility='internal',approved_by=NULL,updated_at=now()",(data['bug_id'],Jsonb(article)))


def verify_for_deployment(c,data,actor,note,now=None):
    validate_tester(data,actor)
    if data.get('status')!='In QA':raise HTTPException(422,'Issue is not awaiting QA')
    lifecycle.validate_testing(data,note)
    now=now or datetime.now(timezone.utc)
    data.update(qa_passed_at=now.isoformat(),verified_by=actor['name'],qa_verified_date=business_date(now).isoformat())
    if not lifecycle.needs_deployment(data):return accept_fix(c,data,actor,note,now)
    developer=user_by_id(c,data['developer_user_id'])
    data.update(status='Ready for Deployment',assignee_user_id=developer['id'],assigned_to=developer['name'],team=developer['team'])
    event(c,data['bug_id'],actor,'testing_passed',{'test_result':note,'assignee_user_id':developer['id']})
    return data

def record_deployment(c,data,actor,releases,now=None):
    if actor['id']!=data.get('developer_user_id') and actor['role'] not in ADMIN_ROLES:raise HTTPException(403,'Only the responsible developer or release administrator can record deployment')
    if data.get('status')!='Ready for Deployment' or not data.get('qa_passed_at'):raise HTTPException(422,'QA acceptance is required before production deployment')
    lifecycle.validate_deployment(data,releases)
    now=now or datetime.now(timezone.utc);tester=user_by_id(c,data['tester_user_id'])
    data.update(status='Ready for Closure',deployed_at=now.isoformat(),assignee_user_id=tester['id'],assigned_to=tester['name'],team=tester['team'])
    event(c,data['bug_id'],actor,'deployed',{'assignee_user_id':tester['id'],'actual_fix_release':data.get('actual_fix_release'),'deployment_ticket_ref':data.get('deployment_ticket_ref')})
    return data
