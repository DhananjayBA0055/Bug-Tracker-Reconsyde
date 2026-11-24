"""Workbook field mapping, validation and date-only calendar SLA calculations."""
from .clock import business_date
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from fastapi import HTTPException

TERMINAL = {'Resolved', 'Closed', 'Rejected - Not a Bug', 'Duplicate'}
EXEMPT = {'Rejected - Not a Bug', 'Duplicate'}
EXTRA_FIELDS = [
 ('issue_type','Issue type','select','Issue Type'),('bucket','Product / process bucket','select','Bucket'),
 ('process_spoc','Process SPOC','text',None),('current_stage','Delivery stage','select','Delivery Stage'),
 ('development_target_date','Development target date','date',None),('bancapp_uat_target_date','Bancapp UAT target date','date',None),
 ('handover_target_date','ProcessDev handover target','date',None),('actual_handover_date','Actual ProcessDev handover','date',None),
 ('process_signoff_date','ProcessDev sign-off','date',None),('tested_by_process_team','Tested by process team','select','Yes/No'),
 ('responded_to_client','Responded to client','select','Yes/No'),
 ('communication_email_date','Email Sent Date / Mail Sent Date','date',None),
 ('bancapp_uat_deployment_date','Bancapp UAT Deployment Date','date',None),
 ('bancapp_uat_signoff_date','Bancapp UAT Sign-off Date','date',None),
 ('processdev_deployment_date','Bancapp ProcessDev Deployment Date','date',None),
 ('client_uat_deployment_date','Client UAT Deployment Date','date',None),
 ('client_production_deployment_date','Client Production Deployment Date','date',None)]

def parse_date(v):
    if not v: return None
    try: return date.fromisoformat(str(v)[:10])
    except ValueError: raise HTTPException(422, 'Dates must use YYYY-MM-DD')

def calculate(data, sla, releases, today=None):
    d = dict(data); today = today or business_date()
    from .request_types import kind
    d['request_kind']=kind(d)
    status = d.get('status'); reported = parse_date(d.get('date_reported'))
    resolved = parse_date(d.get('resolved_date')); closed = parse_date(d.get('closure_date'))
    end = resolved or closed
    d['open_closed'] = 'Closed' if status in TERMINAL else 'Open'
    d['deployment_phase'] = 'Post-Deployment' if str(d.get('detection_stage') or '').startswith('Post:') else 'Pre-Deployment' if str(d.get('detection_stage') or '').startswith('Pre:') else None
    d['age_days'] = max(0, ((end or today)-reported).days) if reported else None
    snapshot=d.get('sla_snapshot')
    rule = snapshot if snapshot and snapshot.get('severity')==d.get('severity') else next((s for s in sla if s['severity'] == d.get('severity')), None)
    due = reported + timedelta(days=int(rule['resolution_days'])) if reported and rule else None
    d['due_date'] = due.isoformat() if due else None
    if status in EXEMPT: d['sla_status'] = 'N/A'
    elif status in TERMINAL and not end: d['sla_status'] = 'Needs resolution date'
    elif not due: d['sla_status'] = 'Unclassified'
    elif end: d['sla_status'] = 'Met' if end <= due else 'Breached'
    elif today > due: d['sla_status'] = 'Breached'
    elif (due-today).days <= 1: d['sla_status'] = 'At Risk'
    else: d['sla_status'] = 'On Track'
    target = releases.get(d.get('target_fix_release'), {})
    actual = releases.get(d.get('actual_fix_release'), {})
    d['target_release_date'] = target.get('planned_date'); d['actual_release_date'] = actual.get('actual_date')
    plan = parse_date(target.get('planned_date')); shipped = parse_date(actual.get('actual_date'))
    d['release_plan_status'] = 'Unplanned' if not target else ('On Plan' if shipped <= plan else 'Slipped') if shipped and plan else 'Overdue' if plan and today > plan and status not in TERMINAL else 'Planned'
    if d['request_kind']!='Bug' and not d.get('sla_snapshot'):
        d['due_date']=None;d['sla_status']='Not Applicable'
    d['review_flags'] = [label for key,label in [('status','Workflow status missing'),('severity','Severity missing'),('priority','Priority missing'),('product_module','Module missing'),('client','Client missing')] if not d.get(key)]
    if status in TERMINAL and status not in EXEMPT and not end: d['review_flags'].append('Resolution date missing')
    if d['request_kind']!='Bug':d['review_flags']=[flag for flag in d['review_flags'] if flag!='Severity missing']
    if status == 'Closed' and not d.get('verified_by'): d['review_flags'].append('QA verification missing')
    return d

def validate_patch(patch, previous, fields, lists, releases):
    allowed = {f['key']:f for f in fields if f['type'] != 'computed'}
    unknown = set(patch)-set(allowed)
    if unknown: raise HTTPException(422, 'Unknown or calculated fields: '+', '.join(sorted(unknown)))
    out = dict(previous)
    for key,value in patch.items():
        f=allowed[key]
        if isinstance(value,(dict,list,bool)): raise HTTPException(422,f"Invalid value for {f['label']}")
        if value is None or str(value).strip() == '': value=None
        elif f['type']=='date': value=parse_date(value).isoformat()
        elif f['type']=='number':
            try:
                number=Decimal(str(value))
                if not number.is_finite() or number<0: raise ValueError()
                if key!='amount_impacted_inr' and number!=number.to_integral_value(): raise ValueError()
                value=str(number.quantize(Decimal('0.01'))) if key=='amount_impacted_inr' else int(number)
            except (InvalidOperation,ValueError): raise HTTPException(422,f"{f['label']} must be a non-negative {'amount' if key=='amount_impacted_inr' else 'integer'}")
        else:
            value=str(value).strip()
            if len(value)>20000: raise HTTPException(422,'Field exceeds 20,000 characters')
            opts=lists.get(f.get('options'),[]) if f.get('options') else []
            if key in {'found_in_release','target_fix_release','actual_fix_release'}: opts=list(releases)
            if (opts or f.get('options') or key.endswith('_release')) and value not in opts and value != previous.get(key):
                raise HTTPException(422,f"Choose a configured value for {f['label']}")
        out[key]=value
    if not out.get('title'): raise HTTPException(422,'Issue title is required')
    if not out.get('date_reported'): raise HTTPException(422,'Date reported is required')
    start=parse_date(out['date_reported'])
    for key in ['resolved_date','closure_date','qa_verified_date','data_correction_completed_on']:
        end=parse_date(out.get(key))
        if end and end<start: raise HTTPException(422,f'{key} cannot precede date reported')
    if out.get('financial_impact')=='Yes' and out.get('severity') not in {'S1 - Critical','S2 - High'}:
        raise HTTPException(422,'Financial impact requires S1 or S2 severity')
    return out


# These values must be produced during the later workflow, not fabricated at intake.
INTAKE_DEFERRED_FIELDS={
    "resolved_date","actual_fix_release","resolution_type","root_cause_category","root_cause_summary",
    "code_ref","deployment_ticket_ref","verified_by","qa_verified_date","data_correction_completed_on",
    "rca_shared","client_confirmation","closed_by","closure_date","closure_remarks","reopen_count",
    "actual_handover_date","process_signoff_date","tested_by_process_team","responded_to_client",
    "bancapp_uat_deployment_date","bancapp_uat_signoff_date","processdev_deployment_date",
    "client_uat_deployment_date","client_production_deployment_date"
}
