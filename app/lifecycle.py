"""Stage-specific business rules derived from the tracker and the team's workflow."""
from .clock import business_date
from copy import deepcopy
from datetime import date
from decimal import Decimal
from fastapi import HTTPException

EXTRA=[
 ('business_justification','Business Justification','textarea',None),
 ('acceptance_criteria','Acceptance Criteria','textarea',None),
 ('action_requested','Action Requested / Business Outcome','textarea',None),
 ('last_working_version','Last Working Build / Version','text',None),
 ('impact_assessment','Impact Assessment','select','Impact Assessment'),
 ('impact_notes','Impact Details / Assessment Notes','textarea',None),
 ('release_blocker_reason','Release Blocker Reason','textarea',None),
 ('data_correction_plan','Data Correction Scope & Plan','textarea',None),
 ('developer_test_evidence','Developer Test Evidence Ref','text',None),
 ('regression_test_ref','Regression Test Ref','text',None),
 ('regression_test_result','Regression Test Result','select','Test Result'),
 ('qa_test_evidence','QA / Designer Test Evidence Ref','text',None),
 ('deployment_evidence','Deployment Evidence Ref','text',None),
 ('client_confirmation_ref','Client Confirmation Evidence Ref','text',None),
 ('rca_shared_ref','RCA Communication Evidence Ref','text',None),
 ('duplicate_of_issue_id','Duplicate Of Bug ID','text',None),
 ('repeat_signature','Problem Family / Repeat Signature','text',None),
 ('prevention_action','Preventive / Recurrence Action','textarea',None),
 ('verification_steps','Fix Verification / L1 Check Steps','textarea',None),
]
FIX_FIELDS={'prevention_action','verification_steps','resolution_type','root_cause_category','code_ref','deployment_ticket_ref','target_fix_release','actual_fix_release','post_deploy_action','data_correction_plan','developer_test_evidence','regression_test_ref','duplicate_of_issue_id','repeat_signature'}
TEST_FIELDS={'qa_test_evidence','regression_test_result','client_confirmation','client_confirmation_ref','rca_shared','rca_shared_ref','data_correction_completed_on','closure_remarks','test_evidence_ref','tested_by_process_team'}
DEPLOY_FIELDS={'actual_fix_release','deployment_ticket_ref','deployment_evidence','post_deploy_action','client_production_deployment_date','client_uat_deployment_date','bancapp_uat_deployment_date','processdev_deployment_date','actual_handover_date','data_correction_completed_on'}
MILESTONE_FIELDS={'actual_handover_date','bancapp_uat_deployment_date','bancapp_uat_signoff_date','processdev_deployment_date','process_signoff_date','client_uat_deployment_date','communication_email_date','responded_to_client','current_stage'}
CONTROLLED=MILESTONE_FIELDS|FIX_FIELDS|TEST_FIELDS|DEPLOY_FIELDS|{'developer_resolution','developer_rca','resolution_author_id','verified_by','qa_verified_date','closed_by','closure_date','resolved_date','closed_at','qa_passed_at','deployed_at'}
POLICY_LISTS={'Impact Assessment':['Under assessment','Quantified'],'Test Result':['Passed','Failed','Not Applicable']}

def require_values(data,keys,message):
    missing=[k for k in keys if data.get(k) is None or not str(data.get(k)).strip()]
    if missing:raise HTTPException(422,message+': '+', '.join(missing))

def validate_intake(data,client=False,today=None):
    today=today or business_date()
    required=['title','client','environment','steps_to_reproduce','expected_result','actual_result']
    from .request_types import kind
    is_bug=kind(data)=='Bug'
    if not is_bug:
        required=['title','client','environment','business_justification','acceptance_criteria','expected_result']
        if not client:required+=['product_module','priority']
    if not client and is_bug:required+=['date_reported','source','bug_scope','product_module','recon_type','detection_stage','bug_category','severity','priority']
    require_values(data,required,'Complete the reporting information')
    if data.get('date_reported') and date.fromisoformat(data['date_reported'])>today:raise HTTPException(422,'Date reported cannot be in the future')
    if data.get('regression')=='Yes':require_values(data,['last_working_version'],'A regression needs the last working version')
    if data.get('release_blocker')=='Yes':require_values(data,['release_blocker_reason'],'Explain why this blocks release')
    if data.get('financial_impact')=='Yes':
        if data.get('severity') not in {'S1 - Critical','S2 - High'}:raise HTTPException(422,'Financial impact requires S1 or S2')
        require_values(data,['impact_assessment','impact_notes'],'Record the financial-impact assessment')
        if data.get('impact_assessment')=='Quantified':
            require_values(data,['records_affected','amount_impacted_inr'],'Quantified impact needs affected records and amount')
            if int(data['records_affected'])<1:raise HTTPException(422,'Quantified impact requires at least one affected record')
    if data.get('regulatory_impact')=='Yes':require_values(data,['impact_notes'],'Explain the regulatory or audit impact')
    if data.get('data_correction_required')=='Yes':require_values(data,['data_correction_plan'],'Describe the data correction needed')

def freeze_sla(data,rules):
    from .request_types import kind
    if kind(data)!='Bug':return
    rule=next((r for r in rules if r['severity']==data.get('severity')),None)
    if rule:data['sla_snapshot']=deepcopy(rule)

def stage_patch(payload,allowed,fields,lists,releases,data):
    from .domain import validate_patch
    if set(payload)-allowed:raise HTTPException(422,'Fields belong to a different lifecycle stage: '+', '.join(sorted(set(payload)-allowed)))
    updated=validate_patch(payload,data,fields,lists,releases)
    for key,value in payload.items():
        definition=next((f for f in fields if f['key']==key),{})
        if value and definition.get('type')=='date' and date.fromisoformat(str(value))>business_date():raise HTTPException(422,'Actual lifecycle dates cannot be in the future: '+key)
    # Passing fields not in the submitted action cannot overwrite actor or timing evidence.
    return updated

def validate_fix(data,releases,today=None):
    require_values(data,['resolution_type','root_cause_category','developer_test_evidence','verification_steps'],'Fix submission needs classification and developer testing evidence')
    resolution=data['resolution_type']
    if resolution=='Fixed - Code Change':require_values(data,['code_ref'],'Code changes need a PR or commit reference')
    if resolution=='Fixed - Config Change':require_values(data,['deployment_ticket_ref'],'Configuration changes need a change ticket')
    if resolution=='Duplicate':require_values(data,['duplicate_of_issue_id'],'Duplicate resolution needs the original bug ID')
    if data.get('regression')=='Yes':
        require_values(data,['regression_test_ref','prevention_action'],'Include regression-test coverage and preventive action')
    if data.get('environment')=='Production' and data.get('severity') in {'S1 - Critical','S2 - High'}:require_values(data,['prevention_action'],'High-impact production defects need a preventive action')
    if data.get('data_correction_required')=='Yes' or resolution=='Data Correction Only':require_values(data,['data_correction_plan'],'Document the data correction plan')
    if data.get('environment')=='Production' and resolution.startswith('Fixed -'):
        require_values(data,['post_deploy_action'],'Choose how the fix will reach production')
        if resolution=='Fixed - Code Change':require_values(data,['target_fix_release'],'Plan a code-fix release')

def needs_deployment(data):
    return data.get('environment')=='Production' and data.get('resolution_type') in {'Fixed - Code Change','Fixed - Config Change','Data Correction Only'}

def validate_testing(data,note):
    if not str(note or '').strip():raise HTTPException(422,'Record the actual test result')
    require_values(data,['qa_test_evidence'],'Testing requires evidence or a test case reference')
    if data.get('regression')=='Yes' and data.get('regression_test_result')!='Passed':raise HTTPException(422,'The regression test must pass before acceptance')

def validate_deployment(data,releases,today=None):
    today=today or business_date()
    require_values(data,['deployment_ticket_ref','deployment_evidence','client_production_deployment_date'],'Production deployment needs change control, date and evidence')
    if date.fromisoformat(data['client_production_deployment_date'])>today:raise HTTPException(422,'Actual deployment cannot be future-dated')
    if data.get('resolution_type')=='Fixed - Code Change':
        require_values(data,['actual_fix_release'],'Record the release actually shipped')
        release=releases.get(data['actual_fix_release'],{})
        if release.get('status')!='Released' or not release.get('actual_date'):raise HTTPException(422,'The actual fix release must be marked Released with an actual date')
    if data.get('data_correction_required')=='Yes':require_values(data,['data_correction_completed_on'],'Complete the required data correction')

def validate_closure(data):
    require_values(data,['developer_resolution','developer_rca','resolution_author_id','qa_test_evidence'],'Closure requires a developer response and verified testing evidence')
    if needs_deployment(data) and not data.get('deployed_at'):raise HTTPException(422,'QA acceptance is complete, but production deployment must be recorded before closure')
    if data.get('data_correction_required')=='Yes':require_values(data,['data_correction_completed_on'],'Complete the required data correction')
    if data.get('source')=='Client Reported':
        if data.get('client_confirmation')!='Confirmed':raise HTTPException(422,'Client confirmation is required before closure')
        require_values(data,['client_confirmation_ref'],'Record evidence of client confirmation')
        if data.get('environment')=='Production' and data.get('severity') in {'S1 - Critical','S2 - High'}:
            if data.get('rca_shared')!='Yes':raise HTTPException(422,'Share the RCA for a client-reported production S1/S2 issue')
            require_values(data,['rca_shared_ref'],'Record where the RCA was shared')

def close_status(data):return 'Duplicate' if data.get('resolution_type')=='Duplicate' else 'Closed'
