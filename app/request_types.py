"""Canonical request categories; historical IDs and source spellings remain intact."""
KINDS=['Bug','New Requirement','Feature Request','Change Request']
PREFIXES={'Bug':('BUG','bug_number'),'New Requirement':('REQ','requirement_number'),'Feature Request':('FTR','feature_number'),'Change Request':('CHG','change_number')}
def kind(data):
    value=str(data.get('issue_type') or 'Bug').strip().lower()
    if 'feature' in value or 'enhancement' in value:return 'Feature Request'
    if 'requirement' in value:return 'New Requirement'
    if 'change' in value:return 'Change Request'
    return 'Bug'

def summary(rows):
    return [{'request_kind':k,'total':sum(kind(d)==k for d in rows),'open':sum(kind(d)==k and d.get('open_closed')=='Open' for d in rows),'closed':sum(kind(d)==k and d.get('open_closed')=='Closed' for d in rows),'sla_breached':sum(kind(d)==k and d.get('sla_status')=='Breached' for d in rows)} for k in KINDS]
