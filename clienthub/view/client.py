# -*- coding: utf-8 -*-
try:
    import cStringIO as StringIO
except:
    import StringIO

import web
import config
import logging
import csv

import pymongo

import formencode
from formencode import validators
from formencode import htmlfill

from functools import wraps

from corplibs.authenticate import authenticated

from config import app
from config import env
from corplibs.jira_suds import JiraAPI
from corplibs.xgencrowd import CrowdAPI
from corplibs.salesforce import SalesforceAPI
from corplibs.webutils import link
from models import Client

import datetime

jira_api = JiraAPI()
crowd_api = CrowdAPI()
salesforce_api = SalesforceAPI()

_logger = logging.getLogger(__name__)


class ClientList(object):

    # sub-classes should specify:
    #    - title (str)
    #    - table_search (str)

    @authenticated
    def GET(self):
        clients = [Client()._from_db(rec) for rec in config.get_db().clients.find()]
        cs_groups = jira_api.getGroupsInProjectRole('Customer', 'CS')
        cs_groups = set(g['name'] for g in cs_groups)

        web.header('Content-type','text/html')
        return env.get_template('index.html').render(
            clients=clients,
            cs_groups=cs_groups,
            title=self.title,
            table_search=self.table_search,
        )


class ClientHub(ClientList):
    title = 'My Clients'

    table_search = "My Clients"


class AllClients(ClientList):
    title = 'All Clients'

    table_search = ""

class ClientView(object):

    @authenticated
    def GET(self, client_id):
        client = Client(client_id)
        if not client._id:
            raise web.seeother('/clienthub')

        # show the "loading" page
        if 'loadcache' not in web.input() and not client.is_up_to_date():
            web.header('Content-Type', 'text/html')
            return env.get_template('view_loading.html').render(
                client=client
            )
        elif 'loadcache' in web.input():
            client.load_caches()
            raise web.seeother(link(app, 'client.clientview', client._id))

        docs = list(config.get_db().clients.docs.find({'client_id': client._id}).sort([('updated', pymongo.DESCENDING)]))
        web.header('Content-type', 'text/html')
        return env.get_template('view.html').render(
            client=client,
            docs=docs,
        )


class ClientEdit(object):
    @authenticated
    def GET(self, client_id):
        if client_id == 'new':
            client = Client(is_new=True)
        else:
            client = Client(client_id)

        all_groups = crowd_api.get_all_groups()
        cs_groups = jira_api.getGroupsInProjectRole('Customer', 'CS')
        cs_groups = set(g['name'] for g in cs_groups)
        jira_groups = []
        for group in all_groups:
            name = group
            if group in cs_groups:
                name = group + ' (CS)'
            jira_groups.append({'name': name, 'id': group})

        jira_groups.sort(key=lambda x: x['name'].lower())
        jira_groups_expiry = jira_api.getGroupsInProjectRole.get_expiry('Customer', 'CS')
        all_groups_expiry = crowd_api.get_all_groups.get_expiry()
        groups_expiry = min([date for date in (jira_groups_expiry, all_groups_expiry) if date] or [None])

        sf_accounts = salesforce_api.get_accounts()
        sf_accounts.sort(key=lambda x: x['name'].lower())
        sf_expiry = salesforce_api.get_accounts.get_expiry()

        xgenners = crowd_api.get_users_for_group('10gen')
        xgenners.sort(key=lambda x: x['displayName'])
        xgenners_expiry = crowd_api.get_users_for_group.get_expiry('10gen')

        web.header('Content-type', 'text/html')
        return env.get_template('edit.html').render(
            client=client,
            groups=jira_groups,
            sf_accounts=sf_accounts,
            xgenners=xgenners,
            message=web.input().get('message', None),
            sf_expiry=sf_expiry,
            groups_expiry=groups_expiry,
            xgenners_expiry=xgenners_expiry,
        )

    @authenticated
    def POST(self, client_id):
        if client_id == 'new':
            client = Client(is_new=True)
        else:
            client = Client(client_id)

        try:
            params = web.input(secondary_engs=[], associated_jira_groups=[])
            params.pop('message', None)

            clean_data = ClientForm.to_python(params)
        except validators.Invalid, e:
            out_html = self.GET(client_id)
            web.header('Content-type', 'text/html')
            return htmlfill.render(out_html, defaults=web.input(), errors=e.error_dict, force_defaults=False)

        for key, value in clean_data.iteritems():
            if key == 'associated_jira_groups':
                value = [{'name': v} for v in value]
            setattr(client, key, value)

        if client.sf_account_id:
            # set the account_contact to the jira
            # username of the person who is the
            # owner in salesforce
            account = client.get_sf_account()
            owner_email = account['owner_email']
            crowd_user = crowd_api.get_user_by_email(owner_email)
            jira_username = crowd_user.get('username')

            client.account_contact_email = owner_email
            if jira_username:
                client.account_contact = jira_username
            else:
                client.account_contact = None

        else:
            client.account_contact = None
            client.sf_account_id = None
            client.sf_account_name = None

        client_doc = client._fields_dict()

        # remove empty string values
        for key, value in client_doc.items():
            if hasattr(value, 'strip') and value.strip() == '':
                del client_doc[key]

        client_doc['updated'] = datetime.datetime.utcnow()
        _id = config.get_db().clients.save(client_doc)
        raise web.seeother(link(config.app, 'client.clientview', _id))

class ClientForm(formencode.Schema):
    allow_extra_fields = True

    name = validators.NotEmpty()

class ClientCacheRefresh(object):

    cache_key = {
        'all_groups': lambda: crowd_api.get_all_groups.expire(),
        'xgenners': lambda: crowd_api.get_users_for_group.expire('10gen'),
        'jira_groups': lambda: jira_api.getGroupsInProjectRole.expire('Customer','CS'),
        'sf_accounts': lambda: salesforce_api.get_accounts.expire(),
    }

    @authenticated
    def GET(self, client_id, cache_types):
        client = Client(client_id)

        for cache_type in cache_types.split(','):
            if cache_type in self.cache_key:
                expirer = self.cache_key[cache_type]
                expirer()
            else:
                client.expire(cache_type)

        if 'HTTP_REFERER' in web.ctx.environ:
            raise web.seeother(web.ctx.environ['HTTP_REFERER'])
        else:
            raise web.seeother(link('clientview', client._id))

class ClientDelete(object):

    @authenticated
    def GET(self, client_id):
        client = Client(client_id)
        if not client._id:
            raise web.seeother(link('clienthub'))

        config.get_db().clients.docs.remove({'client_id': client._id})
        config.get_db().clients.remove({'_id': client._id})

        raise web.seeother(link(config.app, 'clienthub'))


class ExportClientView(object):

    @authenticated
    def GET(self, client_id):
        client = Client(client_id)
        if not client._id:
            raise web.seeother('/clienthub')

        contacts = client.get_contacts()
        issues = jira_api.get_issues_related_to_group(client.jira_group, 1000)
        issues = client.get_jira_cases_with_extras(limit=None, jira_cases=issues)
        for issue in issues:
            status = issue.get('status',{})
            priority = issue.get('priority',{})
            #sometimes we get a string rather than a hash
            try:
                issue['status_name'] = unicode(status.get('name', ''))
            except:
                issue['status_name'] = unicode(status)
            try:
                issue['priority_name'] = unicode(priority.get('name', ''))
            except:
                issue['priority_name'] = unicode(priority)

            try:
                issue['updated'] = issue['updated'].strftime('%Y-%m-%d %I:%M %p')
            except:
                issue['updated'] = ""

        contact_keys = ['name', 'title', 'phone', 'email', 'is_sfdc', 'jira_username']

        jira_keys = ['key', 'reporter', 'assignee_fullname', 'priority_name', 'summary', 'status_name', 'updated', 'votes',
                     'description', 'project', 'created', 'fixVersions',
                     'components', 'affectsVersions', 'summary', 'resolution', 'duedate']


        web.header('Content-type', 'text/csv')
        web.header('Content-disposition', "attachment; filename=%s.csv" % client.name)
        csv_file = StringIO.StringIO()
        writer = csv.DictWriter(csv_file, contact_keys, extrasaction="ignore", quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(contacts)
        csv_file.write('\n')



        writer = csv.DictWriter(csv_file, jira_keys, extrasaction="ignore", quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(issues)
        csv_file.seek(0)

        return csv_file
