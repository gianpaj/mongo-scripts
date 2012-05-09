from datetime import datetime

import web
app = web.config.app
env = web.config.env
db = web.config.wwwdb

import formencode
from formencode import validators
from formencode import htmlfill

from commonweb.util.integration import set_cache_usage


from .utils import link
#from xgen.admin.auth import requires_login


from .models import Client

from .utils import jira_api, salesforce_api, crowd_api


def invalidate_clienthub_cache(group_name):
    for record in db.clients.find({'jira_group': group_name}):
        client = Client()._from_db(record)
        client.expire('contacts')

class UniqueJiraGroupName(formencode.FancyValidator):
    def _to_python(self, value, state):
        if not value:
            raise formencode.Invalid(
                "Must set group name",
                value, state)
        set_cache_usage(False, True)
        group = jira_api.getGroup(value)
        set_cache_usage(True, True)
        if group:
            raise formencode.Invalid(
                "Group '%s' already exists" % value,
                value, state)

        return value

class UniqueJiraUsername(formencode.FancyValidator):
    def _to_python(self, value, state):
        value = value.lower()

        set_cache_usage(False, True)
        user = jira_api.getUser(value)
        set_cache_usage(True, True)
        if user:
            raise formencode.Invalid(
                "User '%s' already exists" % value,
                value, state)

        return value

class ExistingJiraUsername(formencode.FancyValidator):
    def _to_python(self, value, state):
        value = value.lower()

        set_cache_usage(False, True)
        user = jira_api.getUser(value)
        set_cache_usage(True, True)
        if not user:
            raise formencode.Invalid(
                "User '%s' does not exist" % value,
                value, state)

        return value

class NewGroupValidator(formencode.Schema):
    group_name = UniqueJiraGroupName()
    is_cs = validators.StringBool(if_missing=False)

    first_user_username = UniqueJiraUsername()
    first_user_realname = validators.String()
    first_user_email = validators.Email()

    def _to_python(self, value, state):
        value = super(NewGroupValidator, self)._to_python(value, state)
        # require that username is set if realname or email
        # are also set
        if value.get('first_user_realname', None) or value.get('first_user_email', None):
            if not value.get('first_user_username', None):
                raise formencode.Invalid(
                    "Must set username if adding a user", value, state,
                    error_dict={'first_user_username': "Must set username if adding a user"}
                )
        return value

class UserValidator(formencode.Schema):
    username = validators.String()
    realname = validators.String(if_missing='')
    email = validators.Email(if_missing='')
    is_new = validators.StringBool()

    def _to_python(self, value, state):
        value = super(UserValidator, self)._to_python(value, state)
        value['username'] = value['username'].lower()

        if not value['is_new']:
            # existing user
            value['username'] = ExistingJiraUsername().to_python(value['username'])
            value['is_new'] = False

        elif not (value['realname'] and value['email']):
            # require all fields
            value['username'] = UniqueJiraUsername().to_python(value['username'])
            err = {}
            if not value['realname']:
                err['realname'] = "Must set real name if adding a user"
            if not value['email']:
                err['email'] = "Must set email if adding a user"
            raise formencode.Invalid(
                "Real name and email required", value, state,
                error_dict=err)

        return value


class JiraTool(app.page):
    path = '/clienthub/jira'

    #@requires_login
    def GET(self):
        groups = crowd_api.get_all_groups()
        cs_groups = jira_api.getGroupsInProjectRole('Customer', 'CS')
        cs_groups = set([g['name'] for g in cs_groups])

        expiry = min(
            crowd_api.get_all_groups.get_expiry() or datetime(1970,1,1),
            jira_api.getGroupsInProjectRole.get_expiry('Customer', 'CS') or datetime(1970,1,1)
        )
        if expiry == datetime(1970,1,1):
            expiry = None

        groups = [{'name': group, 'is_cs': group in cs_groups} for group in groups]

        web.header('Content-Type', 'text/html')
        return env.get_template('clienthub/jira.html').render(
            groups=groups,
            expiry=expiry,
        )

class JiraGroup(app.page):
    path = '/clienthub/jira/(.+)'

    #@requires_login
    def GET(self, group_name):
        group = jira_api.getGroupDetails(group_name)
        expiry = jira_api.getGroupDetails.get_expiry(group_name)

        cs_groups = jira_api.getGroupsInProjectRole('Customer', 'CS')
        cs_groups = set([g['name'] for g in cs_groups])
        group['is_cs'] = bool(group['name'] in cs_groups)

        related_clients = db.clients.find({'jira_group': group_name})
        related_clients = [Client()._from_db(r) for r in related_clients]

        web.header('Content-Type', 'text/html')
        return env.get_template('clienthub/jiragroup.html').render(
            group=group,
            expiry=expiry,
            related_clients=related_clients,
        )

class NewJiraGroup(app.page):
    path = '/clienthub/jira/new'

    #@requires_login
    def GET(self):
        web.header('Content-Type', 'text/html')
        return env.get_template('clienthub/jiranew.html').render()

    #@requires_login
    def POST(self):
        params = dict(web.input())
        try:
            clean = NewGroupValidator().to_python(params)
        except formencode.Invalid, e:
            errors = e.error_dict
            html = env.get_template('clienthub/jiranew.html').render()
            web.header('Content-Type', 'text/html')
            return htmlfill.render(html, defaults=params, errors=errors)

        if clean.get('first_user_username', None):
            # first create the user
            user = jira_api.create_user(
                clean.get('first_user_username', None),
                clean.get('first_user_realname', None),
                clean.get('first_user_email', None))
        else:
            user = None

        group = jira_api.create_group(clean['group_name'], user, clean['is_cs'])

        # after we do this, have to expire a few caches so
        # the UI catches up when we redirect
        crowd_api.get_all_groups.expire()
        jira_api.getGroupsInProjectRole.expire('Customer', 'CS')

        raise web.seeother(link('jiragroup', clean['group_name']))

class AddJiraUserToGroup(app.page):
    path = '/clienthub/jira/(.+)/adduser'

    #@requires_login
    def GET(self, group_name):
        web.header('Content-Type', 'text/html')
        return env.get_template('clienthub/jiraadduser.html').render(
            group_name=group_name,
        )

    #@requires_login
    def POST(self, group_name):
        params = web.input()
        try:
            clean = UserValidator().to_python(params)
        except formencode.Invalid, e:
            errors = e.error_dict
            msg = e.msg
            is_new = params.get('is_new') == 'true'
            html = env.get_template('clienthub/jiraadduser.html').render(group_name=group_name, msg=msg, is_new=is_new)
            web.header('Content-Type', 'text/html')
            return htmlfill.render(html, defaults=params, errors=errors)

        if clean['is_new']:
            user = jira_api.create_user(
                clean['username'],
                clean['realname'],
                clean['email']
            )
        else:
            user = jira_api.getUser(clean['username'])

        jira_api.add_user_to_group(group_name, user)

        # expire the cache before redirecting
        jira_api.getGroupDetails.expire(group_name)
        invalidate_clienthub_cache(group_name)

        raise web.seeother(link('jiragroup', group_name))

class RemoveJiraUserFromGroup(app.page):
    path = '/clienthub/jira/(.+)/remove/(.+)'

    #@requires_login
    def GET(self, group_name, username):
        jira_api.remove_user_from_group(group_name, username)

        # expire the cache before redirecting
        jira_api.getGroupDetails.expire(group_name)
        invalidate_clienthub_cache(group_name)

        raise web.seeother(link('jiragroup', group_name))

class DeleteJiraUser(app.page):
    path = '/clienthub/jira/(.+)/delete/(.+)'

    #@requires_login
    def GET(self, group_name, username):
        jira_api.delete_user(username)

        # expire the cache before redirecting
        jira_api.getGroupDetails.expire(group_name)
        invalidate_clienthub_cache(group_name)

        raise web.seeother(link('jiragroup', group_name))

class JiraRefresh(app.page):
    path = '/clienthub/jira/_refresh'

    #@requires_login
    def GET(self):
        crowd_api.get_all_groups.expire()
        jira_api.getGroupsInProjectRole.expire('Customer', 'CS')

        if web.input().get('next'):
            raise web.seeother(web.input().get('next'))

        raise web.seeother(link('jiratool'))

class DeleteJiraGroup(app.page):
    path = '/clienthub/jira/(.+)/delete'

    #@requires_login
    def GET(self, group_name):
        group = jira_api.getGroupDetails(group_name)
        if group['users']:
            raise web.seeother(link('jiragroup', group_name))

        # have to delete from both; in some cases,
        # deleting from JIRA doesn't delete from Crowd
        for api in [jira_api, crowd_api]:
            try:
                api.delete_group(group_name)
            except:
                app.log_current_exception()

        # after we do this, have to expire a few caches so
        # the UI catches up when we redirect
        crowd_api.get_all_groups.expire()
        jira_api.getGroupsInProjectRole.expire('Customer', 'CS')

        raise web.seeother(link('jiratool'))

class RefreshJiraGroup(app.page):
    path = '/clienthub/jira/(.+)/_refresh'

    #@requires_login
    def GET(self, group_name):
        # expire the cache before redirecting
        jira_api.getGroupDetails.expire(group_name)
        invalidate_clienthub_cache(group_name)

        raise web.seeother(link('jiragroup', group_name))

class ToggleCSJiraGroup(app.page):
    path = '/clientjub/jira/(.+)/togglecs'

    def GET(self, group_name):
        jira_api.getGroupsInProjectRole.expire('Customer', 'CS')
        cs_groups = [g['name'] for g in jira_api.getGroupsInProjectRole('Customer', 'CS')]

        if group_name in cs_groups:
            jira_api.removeGroupFromProjectRole('Customer', 'CS', group_name)
        else:
            jira_api.addGroupToProjectRole('Customer', 'CS', group_name)

        jira_api.getGroupsInProjectRole.expire('Customer', 'CS')
        raise web.seeother(link('jiragroup', group_name))

