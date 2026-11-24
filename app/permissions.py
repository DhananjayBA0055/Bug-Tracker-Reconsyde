"""Explicit business roles. UI visibility never replaces these server checks."""
ROLES=['super_admin','admin','manager','product_developer','process_designer','quality_analyst','process_developer','client']
TEAMS=['Process Team','Product Team','QA Team']
PERMISSIONS=['raise','edit','reassign','fix','test_close','comment','attach','reports','performance','manage_users','manage_masters','manage_integrations','manage_releases','publish_knowledge','manage_rights','manage_notifications','edit_notification_templates','manage_notification_overrides']
BASE={
 'super_admin':PERMISSIONS,
 'admin':PERMISSIONS,
 'manager':['reports','performance'],
 'product_developer':['edit','reassign','fix','comment','attach','reports'],
 'process_developer':['edit','reassign','fix','comment','attach','reports'],
 'process_designer':['raise','edit','reassign','test_close','comment','attach','reports','publish_knowledge'],
 'quality_analyst':['raise','edit','reassign','test_close','comment','attach','reports','publish_knowledge'],
 'client':['raise','comment','attach','reports'],
}
DEV_ROLES={'product_developer','process_developer'}
ADMIN_ROLES={'admin','super_admin'}
def effective(user,configured=None):
    if user['role']=='super_admin':return set(PERMISSIONS)
    rights=set((configured or BASE).get(user['role'],[]))
    for k,v in (user.get('permissions') or {}).items():
        if k in PERMISSIONS:
            if v:rights.add(k)
            else:rights.discard(k)
    return rights
def team_for(role):
    return {'product_developer':'Product Team','process_developer':'Process Team','process_designer':'Process Team','quality_analyst':'QA Team'}.get(role,'')
