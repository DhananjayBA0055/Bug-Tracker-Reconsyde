from datetime import date
import json
from pathlib import Path
import pytest
from fastapi import HTTPException
from app.domain import calculate,validate_patch,EXTRA_FIELDS
from app.main import can_read,visible,hash_password,verify_password,safe_csv,SEED,FIELDS

SLA=SEED['sla']
TODAY=date(2026,11,17)
def base(**kw):return {'title':'Reconciliation issue','date_reported':'2026-11-10','status':'In Progress','severity':'S3 - Medium',**kw}
def calc(**kw):return calculate(base(**kw),SLA,{},TODAY)

def test_calendar_sla_at_risk_on_due_day():
    d=calc();assert d['due_date']=='2026-11-17';assert d['sla_status']=='At Risk'
def test_breach_after_due_day():assert calc(date_reported='2026-11-09')['sla_status']=='Breached'
def test_on_track():assert calc(date_reported='2026-11-16')['sla_status']=='On Track'
def test_resolved_on_due_date_is_met():assert calc(status='Resolved',resolved_date='2026-11-17')['sla_status']=='Met'
def test_resolved_late_is_breached():assert calc(status='Resolved',resolved_date='2026-11-18')['sla_status']=='Breached'
def test_closed_without_date_needs_review():
    d=calc(status='Closed');assert d['sla_status']=='Needs resolution date';assert 'Resolution date missing' in d['review_flags']
def test_missing_severity_is_not_met():assert calc(severity=None)['sla_status']=='Unclassified'
def test_missing_status_remains_missing():
    d=calc(status=None);assert d['status'] is None;assert 'Workflow status missing' in d['review_flags'];assert d['open_closed']=='Open'
@pytest.mark.parametrize('status',['Rejected - Not a Bug','Duplicate'])
def test_exempt(status):assert calc(status=status)['sla_status']=='N/A'
def test_resolved_age_stops():assert calc(status='Resolved',resolved_date='2026-11-12')['age_days']==2
def test_detection_stage():
    assert calc(detection_stage='Post: Production - BAU')['deployment_phase']=='Post-Deployment'
    assert calc(detection_stage='Pre: UAT')['deployment_phase']=='Pre-Deployment'
    assert calc(detection_stage=None)['deployment_phase'] is None
def test_release_plan():
    rel={'REL-A':{'planned_date':'2026-11-12'},'REL-B':{'actual_date':'2026-11-13'}}
    assert calculate(base(target_fix_release='REL-A'),SLA,rel,TODAY)['release_plan_status']=='Overdue'
    assert calculate(base(target_fix_release='REL-A',actual_fix_release='REL-B'),SLA,rel,TODAY)['release_plan_status']=='Slipped'
    rel['REL-B']['actual_date']='2026-11-12'
    assert calculate(base(target_fix_release='REL-A',actual_fix_release='REL-B'),SLA,rel,TODAY)['release_plan_status']=='On Plan'
def test_template_releases_are_not_live():assert calc(target_fix_release='REL-4.2.0')['target_release_date'] is None

def validate(patch,previous=None):return validate_patch(patch,previous or base(),FIELDS,SEED['lists'],{})
@pytest.mark.parametrize('patch',[{'severity':'invented'},{'amount_impacted_inr':-1},{'records_affected':1.2},{'due_date':'2026-01-01'},{'title':''},{'resolved_date':'2026-01-01'},{'title':{'x':1}},{'financial_impact':'Yes','severity':'S3 - Medium'},{'amount_impacted_inr':'NaN'},{'target_fix_release':'REL-4.2.0'}])
def test_invalid_patch_rejected(patch):
    with pytest.raises(HTTPException):validate(patch)
def test_amount_keeps_decimal_precision():assert validate({'amount_impacted_inr':'1234567890.12'})['amount_impacted_inr']=='1234567890.12'
def test_financial_impact_high_severity():assert validate({'financial_impact':'Yes','severity':'S2 - High'})['severity']=='S2 - High'
def test_unknown_legacy_value_can_be_retained():assert validate({'client':'Mau'},base(client='Mau'))['client']=='Mau'
def test_password_hash_and_verify():
    h=hash_password('Strong-Password-123!');assert verify_password('Strong-Password-123!',h);assert not verify_password('wrong',h)
@pytest.mark.parametrize('v',['=HYPERLINK("evil")','+cmd','-2','@SUM(A1)','  =1+1'])
def test_csv_formula_injection(v):assert safe_csv(v).startswith("'")
def test_csv_plain_value():assert safe_csv('FCB')=='FCB'
def test_client_access():
    u={'role':'client','clients':['NPCI']}
    assert can_read(u,{'client':'NPCI, SMFG'})
    assert not can_read(u,{'client':'FCB'})
    assert not can_read(u,{'client':'All'})
    assert not can_read(u,{'client':None})
    assert not can_read({'role':'client','clients':['All']},{'client':'All'})
def test_client_response_redacts_internal_fields():
    d=visible({'role':'client'},{'bug_id':'BUG-1','title':'x','source_metadata':{'internal':'secret'},'remarks':'private','root_cause_summary':'private','assigned_to':'internal','revision':1})
    assert d=={'bug_id':'BUG-1','title':'x','revision':1}
def test_workbook_data_integrity():
    assert len(SEED['issues'])==99
    assert len({d['bug_id'] for d in SEED['issues']})==99
    assert sum(not d.get('status') for d in SEED['issues'])==57
    assert sum(not d.get('severity') for d in SEED['issues'])==99
    assert len(SEED['fields'])==62
    assert len(SEED['comparison'])==57
    assert len(SEED['source_snapshots'])==3
    assert len(SEED['template_releases'])==5
    assert all(d['source_metadata'] for d in SEED['issues'])
def test_no_calculated_workbook_values_frozen_into_seed():
    computed={f['key'] for f in SEED['fields'] if f['type']=='computed'}
    assert all(not (set(d)&computed) for d in SEED['issues'])

def test_business_date_across_utc_midnight(monkeypatch):
    from app.clock import business_date
    from datetime import datetime,timezone
    monkeypatch.setenv('APP_TIMEZONE','Asia/Kolkata')
    assert business_date(datetime(2026,11,17,19,0,tzinfo=timezone.utc)).isoformat()=='2026-11-18'

def test_sla_snapshot_survives_global_policy_edits():
    from app.domain import calculate
    from app.lifecycle import freeze_sla
    from datetime import date
    d={'title':'test','date_reported':'2026-11-17','status':'In Progress','severity':'S2 - High'}
    freeze_sla(d,[{'severity':'S2 - High','response_hours':4,'resolution_days':3}])
    changed=[{'severity':'S2 - High','response_hours':1,'resolution_days':1}]
    assert calculate(d,changed,{},date(2026,11,18))['due_date']=='2026-11-20'
