from copy import deepcopy
from datetime import datetime,timezone
import pytest
from fastapi import HTTPException
from app.notification_policy import defaults,effective_rule,next_due,render,validate

USER={'id':2,'name':'Developer','role':'product_developer','team':'Product Team'}

def test_scope_precedence_and_mandatory_locks():
    p=defaults();p['groups']=[{'id':'role','name':'Developers','scope':'role','value':'product_developer','rules':{'comment':{'frequency':'daily'}}},{'id':'team','name':'Product Team','scope':'team','value':'Product Team','rules':{'comment':{'frequency':'weekly','locked':True}}}];p['users']={'2':{'rules':{'comment':{'enabled':False,'frequency':'off'}}}}
    r=effective_rule(p,USER,'comment');assert r['frequency']=='weekly' and r['source']=='Product Team' and r['locked']
    p['groups'][1]['rules']['comment']['locked']=False;assert effective_rule(p,USER,'comment')['frequency']=='off'
    p['defaults']['comment']['locked']=True;assert effective_rule(p,USER,'comment')['frequency']=='immediate'

def test_custom_group_priority_is_deterministic():
    p=defaults();p['groups']=[{'id':'z','name':'Later','scope':'custom','members':[2],'priority':2,'rules':{'comment':{'frequency':'weekly'}}},{'id':'a','name':'Earlier','scope':'custom','members':[2],'priority':1,'rules':{'comment':{'frequency':'daily'}}}]
    assert effective_rule(p,USER,'comment')['frequency']=='weekly'

def test_schedule_daily_and_weekly_boundaries():
    p=defaults();p.update(timezone='Asia/Kolkata',daily_time='18:00',weekly_time='17:00',weekly_day=4)
    morning=datetime(2026,11,16,5,tzinfo=timezone.utc)
    assert next_due('daily',morning,p,{})==datetime(2026,11,16,12,30,tzinfo=timezone.utc)
    assert next_due('daily',datetime(2026,11,16,13,tzinfo=timezone.utc),p,{})==datetime(2026,11,17,12,30,tzinfo=timezone.utc)
    assert next_due('weekly',morning,p,{})==datetime(2026,11,20,11,30,tzinfo=timezone.utc)
    assert next_due('weekly',datetime(2026,11,20,12,tzinfo=timezone.utc),p,{})==datetime(2026,11,27,11,30,tzinfo=timezone.utc)

def test_text_templates_substitute_only_known_data():
    result=render({'subject':'{{issue_id}} — {{event_name}}','body':'Hello {{recipient_name}}\n{{items}}'},{'issue_id':'REQ-0001','event_name':'Changed','recipient_name':'Pat','items':'<script>sample</script>'})
    assert result['subject']=='REQ-0001 — Changed';assert '<script>sample</script>' in result['body'] # Plain text, never executed as a template.

@pytest.mark.parametrize('change',[lambda p:p['templates']['created'].update(body='{{password}}'),lambda p:p['templates']['created'].update(subject='Invalid\nSubject'),lambda p:p.update(timezone='Unknown/Timezone'),lambda p:p.update(daily_time='25:10'),lambda p:p['defaults']['comment'].update(frequency='hourly'),lambda p:p['defaults']['tray_report'].update(frequency='immediate')])
def test_invalid_policies_are_rejected(change):
    p=defaults();change(p)
    with pytest.raises(HTTPException):validate(p,[USER])
