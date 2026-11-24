"""Real HTTP/PostgreSQL checks; TEST_DATABASE_URL must be an empty disposable database."""
import io,os
from datetime import datetime,timedelta,timezone,date
import pytest
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from openpyxl import load_workbook
from app.permissions import BASE

pytestmark=pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'),reason='Requires disposable PostgreSQL')
PASSWORD='Disposable-Test-Password-456!'

@pytest.fixture(scope='module')
def env():
    import app.main as m
    old=m.DB_URL;m.DB_URL=os.environ['TEST_DATABASE_URL'];m.COOKIE_SECURE=False
    os.environ.update(ADMIN_EMAIL='qa-admin@example.com',ADMIN_PASSWORD=PASSWORD,SETTINGS_ENCRYPTION_KEY=Fernet.generate_key().decode())
    with m.db() as c:assert c.execute("SELECT count(*) AS n FROM information_schema.tables WHERE table_schema='public'").fetchone()['n']==0,'Use an EMPTY disposable database'
    with TestClient(m.app) as admin:
        r=admin.post('/api/login',json={'email':'qa-admin@example.com','password':PASSWORD});assert r.status_code==200,r.text
        admin.headers['X-CSRF-Token']=r.json()['csrf'];people={};clients={}
        for role in ['product_developer','process_developer','process_designer','quality_analyst','manager','admin','client']:
            r=admin.post('/api/users',json={'name':'QA '+role,'email':role+'@example.com','role':role,'password':PASSWORD,'clients':['FCB'] if role=='client' else []});assert r.status_code==201,r.text;people[role]=r.json()
            client=TestClient(m.app);r=client.post('/api/login',json={'email':role+'@example.com','password':PASSWORD});assert r.status_code==200
            client.headers['X-CSRF-Token']=r.json()['csrf'];clients[role]=client
        yield {'admin':admin,'people':people,'clients':clients,'main':m}
        for c in clients.values():c.close()
    m.DB_URL=old

def create(e,route='product',**overrides):
    p=e['people'];d={'title':'Duplicate reference decimals in file parser','date_reported':date.today().isoformat(),'client':'FCB','severity':'S2 - High','priority':'P2 - High','product_module':'File Parser / Format Mapping','developer_user_id':p[route+'_developer']['id'],'tester_user_id':p['quality_analyst' if route=='product' else 'process_designer']['id'],'reported_against_user_id':p[route+'_developer']['id']}
    d.update(current_stage='Development',source='Internal QA',bug_scope='Product / Platform (Core)',recon_type='Not Applicable',environment='UAT',detection_stage='Pre: QA / SIT',bug_category='Functional',steps_to_reproduce='Upload the reference file, run parser, inspect output.',expected_result='References preserved as text.',actual_result='References gain decimal suffixes.');d.update(overrides)
    r=e['clients']['process_designer'].post('/api/issues',json={'data':d});assert r.status_code==201,r.text;return r.json()
def act(e,b,role,action,**kw):return e['clients'][role].post('/api/issues/'+b['bug_id']+'/workflow',json={'revision':b['revision'],'action':action,**kw})
def fix(e,b,route='product'):
    r=act(e,b,route+'_developer','submit_fix',resolution='Treat numeric reference fields as text to avoid duplicate decimals.',rca='Parser inferred a numeric type and added decimal suffixes.',data={'resolution_type':'Fixed - Code Change','root_cause_category':'Code Defect','code_ref':'commit:abc123','developer_test_evidence':'Parser unit tests run 42','verification_steps':'Import the source reference sample; compare exact text output.'});assert r.status_code==200,r.text;return r.json()
def close(e,b,route='product'):
    r=act(e,b,'quality_analyst' if route=='product' else 'process_designer','accept',note='Retested source file and verified text output.',data={'qa_test_evidence':'QA case PARSER-42 passed'});assert r.status_code==200,r.text;return r.json()

def test_seed_roles_and_permissions(env):
    env['main'].initialize();assert env['admin'].get('/api/issues').json()['total']==99
    assert env['admin'].get('/api/me').json()['user']['role']=='super_admin'
    for role in ['manager','product_developer','process_developer']:
        assert env['clients'][role].post('/api/issues',json={'data':{'title':'Forbidden'}}).status_code==403
    assert env['clients']['manager'].get('/api/performance').status_code==200
    assert env['clients']['product_developer'].get('/api/performance').status_code==403

def test_v1_upgrade_preserves_users_and_sets_business_teams(env):
    m=env['main']
    with m.db() as c:
        c.execute('CREATE SCHEMA migration_check')
        c.execute('SET LOCAL search_path TO migration_check')
        c.execute((m.ROOT/'app/schema.sql').read_text())
        for role in ['admin','editor','viewer']:
            c.execute('INSERT INTO users(email,name,password_hash,role) VALUES(%s,%s,%s,%s)',(role+'@upgrade.example',role,'placeholder-hash',role))
        c.execute((m.ROOT/'app/migration_v2.sql').read_text())
        rows=c.execute('SELECT role,team FROM users ORDER BY id').fetchall()
        assert rows[0]['role']=='super_admin'
        assert rows[1]=={'role':'product_developer','team':'Product Team'}
        assert rows[2]['role']=='manager'
        c.execute('SET LOCAL search_path TO public')
        c.execute('DROP SCHEMA migration_check CASCADE')

def test_product_flow_mandatory_rca_tester_and_library(env):
    b=create(env);assert b['bug_id']=='BUG-0100';assert b['workflow_route']=='product'
    assert act(env,b,'product_developer','submit_fix',resolution='Fix',rca='').status_code==422
    assert act(env,b,'process_designer','accept',note='Wrong tester').status_code==403
    b=fix(env,b);assert b['assignee_user_id']==env['people']['quality_analyst']['id']
    assert act(env,b,'product_developer','accept',note='Forbidden').status_code==403
    b=close(env,b);env['closed']=b;assert b['status']=='Closed'
    assert b['bug_id'] in {x['bug_id'] for x in env['admin'].get('/api/knowledge').json()['items']}

def test_process_return_loop_and_response(env):
    b=create(env,'process');r=act(env,b,'process_developer','acknowledge');assert r.status_code==200;b=r.json();b=fix(env,b,'process')
    assert act(env,b,'quality_analyst','accept',note='Wrong route').status_code==403
    r=act(env,b,'process_designer','return',note='Blank reference still fails');assert r.status_code==200,r.text;b=r.json();assert b['return_count']==1
    b=close(env,fix(env,b,'process'),'process')
    with env['main'].db() as c:
        cycles=c.execute('SELECT * FROM work_cycles WHERE issue_id=%s ORDER BY id',(b['bug_id'],)).fetchall();assert len(cycles)==2;assert cycles[0]['responded_at'];assert cycles[0]['returned_at']

def test_reopen_withdraws_article(env):
    b=env['closed'];r=act(env,b,'quality_analyst','reopen',note='Regression detected');assert r.status_code==200,r.text;b=r.json();assert b['reopen_count']==1
    assert b['bug_id'] not in {a['bug_id'] for a in env['admin'].get('/api/knowledge').json()['items']}
    env['closed']=close(env,fix(env,b))

def test_workflow_cannot_be_bypassed_and_concurrency(env):
    b=create(env);c=env['clients']['process_designer'];url='/api/issues/'+b['bug_id']
    assert c.patch(url,json={'revision':b['revision'],'data':{'status':'Closed'}}).status_code==422
    payload={'revision':b['revision'],'data':{'priority':'P1 - Immediate'}}
    assert c.patch(url,json=payload).status_code==200;assert c.patch(url,json=payload).status_code==409
    b=create(env,'process');assert act(env,b,'process_developer','reassign',developer_user_id=env['people']['product_developer']['id'],tester_user_id=env['people']['process_designer']['id']).status_code==422

def test_upload_documents_and_size(env):
    b=create(env);c=env['clients']['process_designer'];url='/api/issues/'+b['bug_id']
    assert c.post(url+'/attachments',files={'file':('evidence.csv',b'key,value\na,1')}).status_code==201
    assert c.post(url+'/attachments',files={'file':('spoof.pdf',b'not PDF')}).status_code==422
    assert c.post(url+'/attachments',files={'file':('bad.exe',b'MZ')}).status_code==422
    assert c.post(url+'/attachments',files={'file':('large.csv',b'a'*(20*1024*1024+1))}).status_code==413
    assert c.post(url+'/comments',json={'body':'Staff note','internal':True}).status_code==201

def test_bulk_users_and_master_management(env):
    data=b'email,name,role,team,active,password\nbulk@example.com,Bulk User,process_developer,Process Team,true,Disposable-Password-123!\n'
    for apply in ['false','true']:
        r=env['admin'].post('/api/bulk/users',files={'file':('users.csv',data)},data={'apply':apply});assert r.status_code==200,r.text
    assert sum(x['email']=='bulk@example.com' for x in env['admin'].get('/api/users').json())==1
    bad=data+b'invalid,Bad,process_developer,Process Team,true,short\n'
    assert env['admin'].post('/api/bulk/users',files={'file':('bad.csv',bad)},data={'apply':'true'}).status_code==422
    for op,value,new in [('add','Test module',''),('rename','Test module','Renamed module'),('delete','Renamed module','')]:
        assert env['admin'].post('/api/masters',json={'group':'Module','operation':op,'value':value,'new_value':new}).status_code==200
    csv=b'group,operation,value,new_value\nModule,add,Bulk Module,\n'
    assert env['admin'].post('/api/bulk/masters',files={'file':('masters.csv',csv)},data={'apply':'true'}).status_code==200

def test_admin_and_last_superadmin_protection(env):
    assert env['clients']['admin'].put('/api/rights',json={'roles':BASE}).status_code==200
    u=env['admin'].get('/api/me').json()['user'];body={k:u[k] for k in ['email','name','role','clients','active']};body['role']='admin'
    assert env['clients']['admin'].put('/api/users/'+str(u['id']),json=body).status_code==403
    assert env['admin'].put('/api/users/'+str(u['id']),json=body).status_code==422

def test_chat_sources_and_client_boundaries(env):
    r=env['clients']['manager'].post('/api/chat',json={'message':'duplicate reference decimals parser'});assert r.status_code==200;assert r.json()['sources']
    client=env['clients']['client'];assert client.get('/api/knowledge').json()['items']==[]
    assert env['admin'].post('/api/knowledge/'+env['closed']['bug_id']+'/publish',json={'visibility':'client_specific'}).status_code==200
    assert client.post('/api/chat',json={'message':'duplicate decimals parser'}).json()['sources']
    assert client.get('/api/archive').status_code==403;assert client.get('/api/performance').status_code==403
    assert all('source_metadata' not in d and 'developer_rca' not in d for d in client.get('/api/issues').json()['items'])

def test_performance_metrics_and_drilldown(env):
    data=env['clients']['manager'].get('/api/performance').json();assert data['tracked_cycles']>0
    p=next(x for x in data['employees'] if x['role']=='process_developer' and x['assigned_bugs']);assert p['returns']==1;assert p['avg_response_hours'] is not None
    assert env['clients']['manager'].get('/api/performance/'+str(p['user_id'])+'/issues').json()

def test_branded_xlsx_and_pdf_reports(env):
    for kind in ['dashboard','issues','clients','performance','knowledge','releases','coverage','users','audit']:
        for fmt in ['xlsx','pdf']:
            r=env['admin'].get('/api/reports/'+kind+'.'+fmt);assert r.status_code==200,(kind,fmt,r.text[:200])
            if fmt=='pdf':assert r.content.startswith(b'%PDF-')
            else:
                wb=load_workbook(io.BytesIO(r.content));assert wb.active['A4'].value.startswith('BancApp Automation');wb.close()

def test_export_filters_and_qa_performance(env):
    r=env['admin'].get('/api/reports/issues.xlsx?status=Closed&client=FCB')
    assert r.status_code==200
    wb=load_workbook(io.BytesIO(r.content));rows=list(wb.active.values);headers=rows[6]
    for row in rows[7:]:
        assert row[headers.index('Status')]=='Closed'
        assert 'FCB' in row[headers.index('Client / Tenant')]
    wb.close()
    employees=env['clients']['manager'].get('/api/performance').json()['employees']
    qa=next(x for x in employees if x['role']=='quality_analyst')
    designer=next(x for x in employees if x['role']=='process_designer')
    assert qa['tests_completed']>0 and qa['avg_test_hours'] is not None
    assert designer['raised_bugs']>0 and designer['tests_completed']>0

def test_email_config_encryption_cc_sla_digest_and_dedup(env,monkeypatch):
    from app import notifications as n
    cfg={'enabled':True,'transport':'smtp_starttls','sender':'support@example.com','host':'smtp.office365.com','port':587,'username':'support@example.com','secret':'Never-Echo-This-Secret','manager_cc':['boss@example.com'],'day_end_hour':0,'day_end_minute':0,'timezone':'Asia/Kolkata'}
    r=env['admin'].put('/api/connections/mail',json={'data':cfg});assert r.status_code==200,r.text;assert 'Never-Echo' not in r.text
    assert 'secret' not in env['admin'].get('/api/connections/mail').json()
    with env['main'].db() as c:stored=env['main'].setting(c,'mail');assert stored['secret']!=cfg['secret'];assert n.decrypt(stored['secret'])==cfg['secret']
    create(env)
    with env['main'].db() as c:n.scheduled(c,datetime.now(timezone.utc)+timedelta(days=5))
    with env['main'].db() as c:first=c.execute('SELECT count(*) AS n FROM notification_outbox').fetchone()['n'];n.scheduled(c,datetime.now(timezone.utc)+timedelta(days=5))
    with env['main'].db() as c:
        assert c.execute('SELECT count(*) AS n FROM notification_outbox').fetchone()['n']==first
        rows=c.execute('SELECT * FROM notification_outbox').fetchall();assert rows;assert all('boss@example.com' in x['cc'] for x in rows)
        assert any('response overdue' in x['subject'] for x in rows);assert any('resolution overdue' in x['subject'] for x in rows);assert any('Day-end' in x['subject'] for x in rows)
    sent=[];monkeypatch.setattr(n,'send',lambda cfg,to,cc,subject,body:sent.append(subject));n.run_once(env['main'].db);assert sent

def test_email_retry_and_csrf(env,monkeypatch):
    from app import notifications as n
    with env['main'].db() as c:n.queue(c,'retry-test',['user@example.com'],['boss@example.com'],'Retry test','body')
    def fail(*a):raise RuntimeError('sensitive provider detail')
    monkeypatch.setattr(n,'send',fail);n.run_once(env['main'].db)
    with env['main'].db() as c:r=c.execute("SELECT * FROM notification_outbox WHERE dedup_key='retry-test'").fetchone();assert r['status']=='retry';assert r['last_error']=='RuntimeError'
    client=env['clients']['process_designer'];old=client.headers.pop('X-CSRF-Token');assert client.post('/api/issues',json={'data':{'title':'Forbidden'}}).status_code==403;client.headers['X-CSRF-Token']=old

def test_reporting_stage_cannot_forge_closure_and_required_fields(env):
    template=create(env)
    base={k:template[k] for k in ['title','client','environment','date_reported','source','bug_scope','product_module','recon_type','detection_stage','bug_category','severity','priority','steps_to_reproduce','expected_result','actual_result','developer_user_id','tester_user_id']}
    c=env['clients']['process_designer']
    for key in ['expected_result','actual_result','steps_to_reproduce','recon_type']:
        d=dict(base);d.pop(key);assert c.post('/api/issues',json={'data':d}).status_code==422,key
    for key,value in [('closure_date',date.today().isoformat()),('developer_rca','Made up'),('qa_test_evidence','not tested'),('resolution_type','Fixed - Code Change')]:
        assert c.post('/api/issues',json={'data':{**base,key:value}}).status_code==422,key
    assert c.post('/api/issues',json={'data':{**base,'regression':'Yes'}}).status_code==422
    assert c.post('/api/issues',json={'data':{**base,'financial_impact':'Yes','severity':'S4 - Low','impact_notes':'money mismatch'}}).status_code==422
    assert c.post('/api/issues',json={'data':{**base,'financial_impact':'Yes','impact_assessment':'Quantified','impact_notes':'incorrect settlement','records_affected':0,'amount_impacted_inr':'0'}}).status_code==422
    r=c.post('/api/issues',json={'data':{**base,'financial_impact':'Yes','impact_assessment':'Under assessment','impact_notes':'Investigating settlement mismatch','watcher_user_ids':[env['people']['manager']['id']]}})
    assert r.status_code==201,r.text;assert r.json()['watcher_user_ids']==[env['people']['manager']['id']]

def test_fix_and_testing_capture_evidence_and_actor_checks(env):
    b=create(env,regression='Yes',last_working_version='2.8')
    payload={'resolution':'Fix parser type mapping','rca':'Incorrect numeric inference','data':{'resolution_type':'Fixed - Code Change','root_cause_category':'Code Defect','developer_test_evidence':'unit tests','verification_steps':'Compare reference strings'}}
    assert act(env,b,'product_developer','submit_fix',**payload).status_code==422
    payload['data'].update(code_ref='commit:def456',regression_test_ref='REG-22',prevention_action='Add a permanent reference-type test')
    r=act(env,b,'product_developer','submit_fix',**payload);assert r.status_code==200,r.text;b=r.json()
    assert act(env,b,'quality_analyst','accept',note='Looks good').status_code==422
    assert act(env,b,'quality_analyst','accept',note='Regression failed',data={'qa_test_evidence':'QA-22','regression_test_result':'Failed'}).status_code==422
    r=act(env,b,'quality_analyst','accept',note='Regression passed',data={'qa_test_evidence':'QA-22','regression_test_result':'Passed'});assert r.status_code==200,r.text;b=r.json()
    assert env['clients']['product_developer'].patch('/api/issues/'+b['bug_id'],json={'revision':b['revision'],'data':{'qa_test_evidence':'forged'}}).status_code==422

def test_production_release_deployment_and_client_closure_gates(env):
    admin=env['admin'];today=date.today().isoformat();release={'release_id':'LIFECYCLE-1','version':'3.1','type':'Hotfix','planned_date':today,'status':'Planned'}
    r=admin.put('/api/releases/LIFECYCLE-1',json=release);assert r.status_code==200,r.text
    b=create(env,source='Client Reported',environment='Production',detection_stage='Post: Production - BAU',target_fix_release='LIFECYCLE-1',release_blocker='Yes',release_blocker_reason='Incorrect exported reference')
    r=act(env,b,'product_developer','submit_fix',resolution='Preserve reference strings',rca='Numeric inference bug',data={'resolution_type':'Fixed - Code Change','root_cause_category':'Code Defect','code_ref':'pr:91','developer_test_evidence':'CI-91','verification_steps':'Run parser smoke test','prevention_action':'Reference string regression suite','post_deploy_action':'Hotfix','target_fix_release':'LIFECYCLE-1'})
    assert r.status_code==200,r.text;b=r.json()
    assert act(env,b,'quality_analyst','accept',note='QA passed',data={'qa_test_evidence':'QA-91'}).status_code==422
    blocked={**release,'revision':1,'status':'Released','actual_date':today};assert admin.put('/api/releases/LIFECYCLE-1',json=blocked).status_code==422
    r=act(env,b,'quality_analyst','verify',note='QA cases passed',data={'qa_test_evidence':'QA-91'});assert r.status_code==200,r.text;b=r.json();assert b['status']=='Ready for Deployment'
    assert admin.put('/api/releases/LIFECYCLE-1',json=blocked).status_code==200
    assert act(env,b,'product_developer','deploy',data={'actual_fix_release':'LIFECYCLE-1'}).status_code==422
    r=act(env,b,'product_developer','deploy',data={'actual_fix_release':'LIFECYCLE-1','deployment_ticket_ref':'CHG-91','deployment_evidence':'Pipeline run 91','client_production_deployment_date':today});assert r.status_code==200,r.text;b=r.json();assert b['status']=='Ready for Closure'
    assert act(env,b,'quality_analyst','accept',note='Production verified').status_code==422
    r=act(env,b,'quality_analyst','accept',note='Production verified; client confirmed',data={'client_confirmation':'Confirmed','client_confirmation_ref':'Client ticket 91 reply','rca_shared':'Yes','rca_shared_ref':'Client ticket 91 RCA attachment'});assert r.status_code==200,r.text;b=r.json();assert b['status']=='Closed'
    r=admin.get('/api/issues/'+b['bug_id']+'/record.xlsx');assert r.status_code==200
    wb=load_workbook(io.BytesIO(r.content));rows=list(wb.active.values);assert any(row[0]=='Developer RCA' and row[1]=='Numeric inference bug' for row in rows);assert any(row[0]=='Deployment Evidence Ref' and row[1]=='Pipeline run 91' for row in rows);wb.close()
    assert admin.get('/api/issues/'+b['bug_id']+'/record.pdf').content.startswith(b'%PDF-')
    # Reopening withdraws the approved answer and resets the verification gate.
    r=act(env,b,'quality_analyst','reopen',note='Regression in production');assert r.status_code==200,r.text;b=r.json();assert not b.get('deployed_at') and not b.get('developer_rca') and not b.get('deployment_evidence') and not b.get('actual_fix_release')

def test_milestone_signoff_requires_designated_tester(env):
    b=create(env,'process');today=date.today().isoformat()
    assert act(env,b,'process_developer','milestones',data={'process_signoff_date':today}).status_code==403
    r=act(env,b,'process_developer','milestones',data={'actual_handover_date':today});assert r.status_code==200,r.text;b=r.json()
    r=act(env,b,'process_designer','milestones',data={'process_signoff_date':today});assert r.status_code==200,r.text
    assert act(env,r.json(),'process_designer','milestones',data={'process_signoff_date':(date.today()+timedelta(days=1)).isoformat()}).status_code==422

def test_client_intake_and_no_internal_assignment(env):
    client=env['clients']['client'];data={'title':'Client source mismatch','client':'FCB','environment':'UAT','steps_to_reproduce':'Run the sample reconciliation','expected_result':'Balanced totals','actual_result':'Unbalanced totals'}
    r=client.post('/api/issues',json={'data':data});assert r.status_code==201,r.text;assert r.json()['status']=='New'
    assert client.post('/api/issues',json={'data':{**data,'developer_user_id':env['people']['product_developer']['id']}}).status_code==403
    assert client.post('/api/issues',json={'data':{**data,'client':'NPCI'}}).status_code==403

def test_admin_and_manager_rbac_for_direct_api_requests(env):
    manager=env['clients']['manager'];dev=env['clients']['product_developer'];client=env['clients']['client']
    for c in [manager,dev,client]:
        assert c.post('/api/masters',json={'group':'Module','operation':'add','value':'Forbidden'}).status_code==403
        assert c.post('/api/bulk/masters',files={'file':('master.csv',b'group,operation,value,new_value\nModule,add,Forbidden,\n')},data={'apply':'true'}).status_code==403
        assert c.put('/api/rights',json={'roles':BASE}).status_code==403
        assert c.put('/api/connections/mail',json={'data':{'enabled':False}}).status_code==403
    for c in [dev,client]:
        assert c.get('/api/reports/performance.xlsx').status_code==403
        assert c.get('/api/performance').status_code==403
    assert manager.get('/api/reports/performance.xlsx').status_code==200

def test_multiple_attachment_categories_and_document_client_isolation(env):
    from pathlib import Path
    b=create(env,client='NPCI');c=env['clients']['process_designer'];url='/api/issues/'+b['bug_id']
    for name,content in [('evidence-one.csv',b'a,b\n1,2'),('evidence-two.csv',b'a,b\n2,3'),('screenshot.png',(env['main'].ROOT/'app/static/bancapp-logo.png').read_bytes())]:
        assert c.post(url+'/attachments',files={'file':(name,content)}).status_code==201
    files=c.get(url).json()['attachments'];assert len(files)==3
    assert sum(f['category']=='supporting_document' for f in files)==2
    assert sum(f['category']=='media' for f in files)==1
    rows=env['admin'].get('/api/documents').json();assert len([r for r in rows if r['issue_id']==b['bug_id']])==2
    outsider=env['clients']['client'];assert all(r['issue_id']!=b['bug_id'] for r in outsider.get('/api/documents').json())
    assert outsider.get('/api/attachments/'+files[0]['id']).status_code==404

def test_employee_specific_exports(env):
    uid=env['people']['product_developer']['id'];r=env['clients']['manager'].get('/api/reports/performance.xlsx?developer_id='+str(uid));assert r.status_code==200,r.text
    wb=load_workbook(io.BytesIO(r.content));rows=list(wb.active.values);data=rows[7:];assert len(data)==1;assert data[0][0]=='QA product_developer';wb.close()

def test_separate_request_types_ids_and_exports(env):
    records=[]
    for kind,prefix in [('New Requirement','REQ-'),('Feature Request','FTR-'),('Change Request','CHG-')]:
        b=create(env,issue_type=kind,business_justification='Reduce manual investigation',acceptance_criteria='Export preserves exact identifiers and includes the audit reference',title=kind+' export enhancement')
        assert b['bug_id'].startswith(prefix);assert b['request_kind']==kind;assert b['due_date'] is None and b['sla_status']=='Not Applicable';records.append(b)
        items=env['admin'].get('/api/issues',params={'request_type':kind}).json()['items'];assert items and all(x['request_kind']==kind for x in items)
        r=env['admin'].get('/api/reports/issues.xlsx',params={'request_type':kind});assert r.status_code==200
        wb=load_workbook(io.BytesIO(r.content));rows=list(wb.active.values);assert all(row[0]==kind for row in rows[7:]);wb.close()
    assert env['admin'].patch('/api/issues/'+records[0]['bug_id'],json={'revision':records[0]['revision'],'data':{'issue_type':'Bug'}}).status_code==422
    summary=env['admin'].get('/api/dashboard').json()['request_type_summary'];assert {r['request_kind'] for r in summary}=={'Bug','New Requirement','Feature Request','Change Request'}

def test_sla_instance_counts_are_attributed_and_deduplicated_without_email(env):
    b=create(env,date_reported=(date.today()-timedelta(days=10)).isoformat());now=datetime.now(timezone.utc)
    with env['main'].db() as c:
        c.execute('UPDATE work_cycles SET assigned_at=%s,response_due_at=%s WHERE issue_id=%s',(now-timedelta(days=10),now-timedelta(days=9),b['bug_id']))
        c.execute("UPDATE issue_events SET created_at=%s WHERE issue_id=%s AND kind='assigned'",(now-timedelta(days=10),b['bug_id']))
    for _ in range(2):
        data=env['clients']['manager'].get('/api/performance').json();person=next(p for p in data['employees'] if p['user_id']==env['people']['product_developer']['id']);assert person['response_sla_breaches']>=1;assert person['resolution_sla_breaches']>=1
    rows=env['clients']['manager'].get('/api/sla-breaches').json();related=[r for r in rows if r['issue_id']==b['bug_id']];assert len(related)==2;assert all(r['user_id']==env['people']['product_developer']['id'] for r in related)

def test_rankings_return_top_three_eligible_people(env):
    b=create(env);now=datetime.now(timezone.utc)
    for i in range(6):
        r=env['admin'].post('/api/users',json={'name':f'Ranking developer {i}','email':f'ranking{i}@example.com','role':'product_developer','password':PASSWORD});assert r.status_code==201
        with env['main'].db() as c:
            for n in range(3):c.execute('INSERT INTO work_cycles(issue_id,developer_id,assigned_at,responded_at,fixed_at) VALUES(%s,%s,%s,%s,%s)',(b['bug_id'],r.json()['id'],now-timedelta(hours=20),now-timedelta(hours=19),now-timedelta(hours=19-i)))
    data=env['clients']['manager'].get('/api/performance').json();assert len(data['best_performers'])==3;assert len(data['worst_performers'])==3
    assert all(p['fix_sample']>=3 for p in data['best_performers']+data['worst_performers'])
    assert [p['avg_fix_hours'] for p in data['worst_performers']]==sorted([p['avg_fix_hours'] for p in data['worst_performers']],reverse=True)

def test_complete_management_dashboard_pdf(env):
    from pypdf import PdfReader
    r=env['admin'].get('/api/reports/dashboard.pdf');assert r.status_code==200,r.text[:200]
    reader=PdfReader(io.BytesIO(r.content));text='\n'.join(p.extract_text() for p in reader.pages)
    for label in ['Request category overview','Client workload','Status distribution','Attention and SLA breaches','Data readiness','Employee performance','Team averages','Top 3 best performers','Top 3 worst performers','Complete current request register']:assert label in text,label
    assert 'New Requirement' in text

def test_user_activity_admin_report_and_login(env):
    r=env['admin'].get('/api/user-activity');assert r.status_code==200;data=r.json();person=next(x for x in data['users'] if x['id']==env['people']['product_developer']['id']);assert person['last_login'];assert person['last_action_at'];assert person['action_count']>0
    assert any(a['action']=='Signed in' for a in data['actions'])
    assert env['clients']['manager'].get('/api/user-activity').status_code==403
    assert env['clients']['product_developer'].get('/api/reports/user_activity.xlsx').status_code==403
    for fmt in ['pdf','xlsx']:assert env['admin'].get('/api/reports/user_activity.'+fmt).status_code==200

def test_master_modify_and_downloadable_formats(env):
    lists=env['admin'].get('/api/settings').json()['lists'];values=lists['Module']+['Modified module example']
    r=env['admin'].post('/api/masters',json={'group':'Module','operation':'modify','values':values});assert r.status_code==200,r.text
    assert 'Modified module example' in env['admin'].get('/api/meta').json()['lists']['Module']
    assert env['admin'].post('/api/masters',json={'group':'Status','operation':'modify','values':['New']}).status_code==422
    assert env['admin'].get('/api/bulk/template/masters.csv').text.strip()=='group,operation,value,new_value'
    r=env['admin'].get('/api/bulk/template/masters');wb=load_workbook(io.BytesIO(r.content));assert list(next(wb.active.values))==['group','operation','value','new_value'];wb.close()
    assert env['clients']['manager'].get('/api/bulk/template/masters.csv').status_code==403

def test_complete_issue_detail_includes_latest_action_and_evidence(env):
    b=create(env);url='/api/issues/'+b['bug_id'];client=env['clients']['process_designer']
    client.post(url+'/attachments',files={'file':('Current_evidence.csv',b'expected,actual\n00123,123.0')})
    client.post(url+'/comments',json={'body':'Latest remarks: awaiting source-file retest'})
    d=client.get(url).json();assert d['attachments'][0]['name']=='Current_evidence.csv';assert d['latest_action']['action']=='Comment added';assert d['issue']['steps_to_reproduce'];assert d['cycles'];assert d['history'];assert d['comments'][-1]['body'].startswith('Latest remarks')

def test_client_can_submit_requirement_with_acceptance_criteria(env):
    c=env['clients']['client'];r=c.post('/api/issues',json={'data':{'title':'Client feature request','issue_type':'Feature Request','client':'FCB','environment':'UAT','business_justification':'Avoid manual export edits','acceptance_criteria':'Add selectable identifier columns and preserve string values','expected_result':'A reusable configurable export'}})
    assert r.status_code==201,r.text;d=r.json();assert d['bug_id'].startswith('FTR-');assert d['sla_status']=='Not Applicable';assert d['status']=='New'

def test_login_history_survives_user_email_edit(env):
    user=env['people']['quality_analyst'];r=env['admin'].put('/api/users/'+str(user['id']),json={'name':user['name'],'email':'quality.changed@example.com','role':'quality_analyst','active':True});assert r.status_code==200,r.text
    data=env['admin'].get('/api/user-activity').json();person=next(p for p in data['users'] if p['id']==user['id']);assert person['last_login'];assert any(a.get('user_id')==user['id'] and a['action']=='Signed in' for a in data['actions'])

@pytest.fixture
def notification_config(env):
    from copy import deepcopy
    old=env['admin'].get('/api/notification-centre').json()['policy']
    draft=deepcopy(old)
    for rule in draft['defaults'].values():rule.update(enabled=False,frequency='off',locked=False)
    draft.update(groups=[],users={},timezone='UTC',daily_time='23:59',weekly_time='17:00',weekly_day=4)
    def save(policy):
        current=env['admin'].get('/api/notification-centre').json()['policy'];policy=deepcopy(policy);policy['revision']=current['revision'];r=env['admin'].put('/api/notification-centre',json={'revision':current['revision'],'policy':policy});assert r.status_code==200,r.text;return r.json()['policy']
    yield draft,save
    save(old)

def test_notification_admin_access_templates_and_revision(env,notification_config):
    from copy import deepcopy
    draft,save=notification_config
    for role in ['manager','product_developer','client']:
        c=env['clients'][role];assert c.get('/api/notification-centre').status_code==403;assert c.post('/api/notification-centre/preview',json={'user_id':env['people']['product_developer']['id'],'event_type':'created'}).status_code==403
    draft['templates']['created']={'subject':'Custom {{issue_id}}','body':'Dear {{recipient_name}}\nStatus {{status}}\n{{app_url}}'};p=save(draft)
    r=env['admin'].post('/api/notification-centre/preview',json={'user_id':env['people']['product_developer']['id'],'event_type':'created','policy':p});assert r.status_code==200,r.text;assert r.json()['subject']=='Custom BUG-0123';assert 'QA product_developer' in r.json()['body'];assert r.json()['sample']
    assert env['admin'].put('/api/notification-centre',json={'revision':p['revision']-1,'policy':p}).status_code==409
    p=deepcopy(p);p['templates']['created']['body']='{{api_key}}';assert env['admin'].put('/api/notification-centre',json={'revision':p['revision'],'policy':p}).status_code==422

def test_group_and_individual_effective_policy_preview(env,notification_config):
    draft,save=notification_config;uid=env['people']['product_developer']['id']
    draft['defaults']['comment'].update(enabled=True,frequency='immediate')
    draft['groups']=[{'id':'product-team','name':'Product mandatory weekly','scope':'team','value':'Product Team','priority':0,'rules':{'comment':{'frequency':'weekly','locked':True}}}]
    draft['users']={str(uid):{'rules':{'comment':{'frequency':'off','enabled':False}}}}
    p=save(draft);r=env['admin'].post('/api/notification-centre/preview',json={'user_id':uid,'event_type':'comment','policy':p});assert r.status_code==200,r.text;rule=r.json()['effective_rule'];assert rule['frequency']=='weekly';assert rule['locked'];assert rule['source']=='Product mandatory weekly'

def test_notification_daily_digest_batches_and_deduplicates(env,notification_config):
    from app.notification_delivery import publish,process
    draft,save=notification_config;draft['defaults']['comment'].update(enabled=True,frequency='daily');draft['templates']['daily_digest']={'subject':'Daily {{item_count}} updates','body':'Hello {{recipient_name}}\n{{items}}'};save(draft)
    b=create(env);now=datetime(2026,11,18,10,tzinfo=timezone.utc)
    with env['main'].db() as c:
        first=publish(c,'comment',b,event_key='daily-policy-1',now=now);second=publish(c,'comment',b,event_key='daily-policy-2',now=now);process(c,now)
        assert c.execute('SELECT count(*) AS n FROM notification_deliveries WHERE event_id=ANY(%s) AND status=\'pending\'',([first,second],)).fetchone()['n']==6
    due=datetime(2026,11,18,23,59,1,tzinfo=timezone.utc)
    with env['main'].db() as c:process(c,due)
    with env['main'].db() as c:
        rows=c.execute("SELECT DISTINCT o.* FROM notification_outbox o JOIN notification_deliveries d ON d.outbox_id=o.id WHERE d.event_id=ANY(%s)",([first,second],)).fetchall();assert len(rows)==3;assert all(r['subject']==f"Daily {len(r['policy_metadata']['event_ids'])} updates" and 'boss@example.com' in r['cc'] for r in rows);assert all(r['body'].count(b['bug_id'])==2 for r in rows);process(c,due)
        assert c.execute('SELECT count(DISTINCT outbox_id) AS n FROM notification_deliveries WHERE event_id=ANY(%s)',([first,second],)).fetchone()['n']==3

def test_weekly_schedule_and_immediate_individual_override(env,notification_config):
    from app.notification_delivery import publish,process
    draft,save=notification_config;uid=env['people']['product_developer']['id'];draft['defaults']['comment'].update(enabled=True,frequency='weekly');draft['users']={str(uid):{'rules':{'comment':{'enabled':True,'frequency':'immediate'}}}};save(draft)
    b=create(env);now=datetime(2026,11,16,10,tzinfo=timezone.utc)
    with env['main'].db() as c:
        event=publish(c,'comment',b,event_key='weekly-policy-1',now=now);process(c,now)
        rows=c.execute('SELECT * FROM notification_deliveries WHERE event_id=%s',(event,)).fetchall();assert sum(r['status']=='queued' for r in rows)==1;assert next(r for r in rows if r['user_id']==uid)['frequency']=='immediate'
        process(c,datetime(2026,11,20,17,0,1,tzinfo=timezone.utc));assert all(r['status']=='queued' for r in c.execute('SELECT * FROM notification_deliveries WHERE event_id=%s',(event,)).fetchall())

def test_disabling_event_cancels_queued_notifications(env,notification_config):
    from app.notification_delivery import publish,process
    draft,save=notification_config;draft['defaults']['comment'].update(enabled=True,frequency='immediate');save(draft);b=create(env)
    with env['main'].db() as c:event=publish(c,'comment',b,event_key='cancel-policy-1');process(c)
    draft['defaults']['comment'].update(enabled=False,frequency='off');save(draft)
    with env['main'].db() as c:
        process(c);rows=c.execute('SELECT * FROM notification_deliveries WHERE event_id=%s',(event,)).fetchall();assert rows and all(r['status']=='suppressed' for r in rows)

def test_template_editor_permission_cannot_change_delivery_policy(env,notification_config):
    from copy import deepcopy
    draft,save=notification_config;save(draft)
    r=env['admin'].post('/api/users',json={'name':'Template Editor','email':'template.editor@example.com','role':'product_developer','permissions':{'edit_notification_templates':True},'password':PASSWORD});assert r.status_code==201
    with TestClient(env['main'].app) as editor:
        r=editor.post('/api/login',json={'email':'template.editor@example.com','password':PASSWORD});editor.headers['X-CSRF-Token']=r.json()['csrf'];p=editor.get('/api/notification-centre').json()['policy'];p['templates']['comment']['body']='Editor text {{issue_id}}'
        assert editor.put('/api/notification-centre',json={'revision':p['revision'],'policy':p}).status_code==200
        p=editor.get('/api/notification-centre').json()['policy'];p['defaults']['comment'].update(enabled=True,frequency='weekly');assert editor.put('/api/notification-centre',json={'revision':p['revision'],'policy':p}).status_code==403

def test_notification_delegation_persists_across_restart(env):
    from copy import deepcopy
    roles=deepcopy(BASE);roles['admin']=[k for k in roles['admin'] if k not in {'manage_notifications','edit_notification_templates','manage_notification_overrides'}]
    try:
        assert env['admin'].put('/api/rights',json={'roles':roles}).status_code==200;env['main'].initialize();assert env['clients']['admin'].get('/api/notification-centre').status_code==403
    finally:assert env['admin'].put('/api/rights',json={'roles':BASE}).status_code==200
