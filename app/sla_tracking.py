"""Count breach instances independently of mail settings and delivery retries."""
from datetime import datetime,time,timedelta,timezone
from zoneinfo import ZoneInfo
import os
from .domain import calculate
from .request_types import kind

def record_breaches(c,now=None):
    now=now or datetime.now(timezone.utc)
    zone=ZoneInfo(os.environ.get('APP_TIMEZONE','Asia/Kolkata'))
    sla=c.execute("SELECT data FROM settings WHERE key='sla'").fetchone()['data']
    for row in c.execute('SELECT id,data FROM issues').fetchall():
        d=row['data']
        if kind(d)!='Bug':continue
        result=calculate(d,sla,{},now.astimezone(zone).date())
        cycles=c.execute('SELECT * FROM work_cycles WHERE issue_id=%s ORDER BY id',(row['id'],)).fetchall()
        for cycle in cycles:
            due=cycle.get('response_due_at')
            if due and (cycle['responded_at'] or cycle['fixed_at'] or cycle['returned_at'] or now)>due:
                c.execute("INSERT INTO sla_breaches(breach_key,issue_id,cycle_id,breach_type,user_id,due_at,detected_at) VALUES(%s,%s,%s,'response',%s,%s,%s) ON CONFLICT DO NOTHING",(f"response:{cycle['id']}",row['id'],cycle['id'],cycle['developer_id'],due,now))
        if result.get('due_date') and result.get('sla_status')=='Breached':
            due=datetime.combine(datetime.fromisoformat(result['due_date']).date(),time.max,tzinfo=zone)
            if now<=due:continue
            events=c.execute('SELECT * FROM issue_events WHERE issue_id=%s AND created_at<=%s ORDER BY created_at,id',(row['id'],due)).fetchall()
            owner=None
            for e in events:
                if e['data'].get('assignee_user_id'):owner=e['data']['assignee_user_id']
                elif e['kind']=='assigned':owner=e['data'].get('developer_id')
                elif e['kind']=='fix_submitted':owner=e['data'].get('tester_id')
            c.execute("INSERT INTO sla_breaches(breach_key,issue_id,breach_type,user_id,due_at,detected_at) VALUES(%s,%s,'resolution',%s,%s,%s) ON CONFLICT DO NOTHING",(f"resolution:{row['id']}:{result['due_date']}",row['id'],owner,due,now))
