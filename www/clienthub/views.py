# -*- coding: utf-8 -*-
from __future__ import with_statement

try:
    import cStringIO as StringIO
except:
    import StringIO

import datetime
import mimetypes
import re
import urllib
import csv

import formencode
from formencode import validators
from formencode import htmlfill
import pymongo
from bson.objectid import ObjectId
from pymongo.errors import OperationFailure
import gridfs

import web
app = web.config.app
env = web.config.env
db = web.config.wwwdb
ftsdb = web.config.ftsdb

from BeautifulSoup import BeautifulSoup
#from xgen.admin.auth import requires_login



import filters
from .utils import link, jira_api, salesforce_api, crowd_api
from .models import Client

from corpbase import authenticated, CorpBase


env.globals.update(link=link)

def auth_user():
    # return the current username, or None
    # if no user is logged in
    c = web.webapi.cookies()
    return c.get("auth_user", None)

env.globals.update(auth_user=auth_user)



jql_url = 'https://jira.mongodb.org/secure/IssueNavigator!executeAdvanced.jspa?runQuery=true&clear=true&jqlQuery='
def _jira_filter(query):
    def do_jira_filter(client):
        if client.jira_group:
            num_params = len(re.findall('%s', query))
            params = tuple([client.jira_group] * num_params)
            return jql_url + urllib.quote(query % params, safe='')
        elif client._id:
            return '/clienthub/edit/%s?message=To+use+JIRA+links,+you+must+assign+a+JIRA+group' % client._id
        else:
            # hopefully we won't get here
            return None
    return do_jira_filter

env.filters['jira_opencases_link'] = _jira_filter('reporter in membersOf("%s") and status not in ("Closed", "Resolved")')
env.filters['jira_allcases_link'] = _jira_filter('reporter in membersOf("%s")')
env.filters['jira_voted_watched_link'] = _jira_filter('reporter in membersOf("%s") or watcher in membersOf("%s") or voter in membersOf("%s")')

def undo_smartquotes(value):
    value = value.replace('\xe2\x80\x99', "'")
    value = value.replace('\xe2\x80\x9c', '"')
    value = value.replace('\xe2\x80\x9d', '"')
    return value

env.filters['undo_smartquotes'] = undo_smartquotes

def extract_legacy_fields(form_template, doc):
    # we have to render the template here, since the
    # doc template may use macros; this will be safer
    # than trying to manually parse the macros out.
    html = env.get_template(form_template).render(
        client=Client(),
        doc={},
        legacy_fields={},
    )

    non_legacy_fields = set()

    soup = BeautifulSoup(html)
    for field in soup.findAll(['input', 'select', 'textarea']):
        name = field.get('name', None)
        if name:
            non_legacy_fields.add(name)

    internal_fields = set(['_id', 'client_id', '_type', 'web_user', '_legacy'])

    unused_fields = {}
    for field_name in doc.keys():
        if field_name not in non_legacy_fields and field_name not in internal_fields:
            unused_fields[field_name] = doc.pop(field_name)

    return unused_fields


class ClientList(object):

    # sub-classes should specify:
    #    - title (str)
    #    - table_search (str)

    @authenticated
    def GET(self, pageParams, *args):
        clients = [Client()._from_db(rec) for rec in db.clients.find()]

        cs_groups = jira_api.getGroupsInProjectRole('Customer', 'CS')
        cs_groups = set(g['name'] for g in cs_groups)

        web.header('Content-type','text/html')
        return env.get_template('clienthub/index.html').render(
            clients=clients,
            cs_groups=cs_groups,
            title=self.title,
            table_search=self.table_search,
        )

class ClientHub(app.page, CorpBase, ClientList):
    path = '/clienthub'
    title = 'My Clients'

    table_search = "My Clients"

class AllClients(app.page, CorpBase, ClientList):
    path = '/clienthub/all'
    title = 'All Clients'

    table_search = ""

class ClienthubRedirector(app.page, CorpBase):
    path = '/clienthub/link/(.+)/(.+)'

    @authenticated
    def GET(self, pageParams, identifier_type, identifier, *args):
        if identifier_type in ('jira', 'jira_group'):
            clients = db.clients.find({'jira_group': identifier})
        elif identifier_type == 'name':
            clients = db.clients.find({'name': identifier})
        else:
            # redirect to the search page
            raise web.seeother(link('allclients', q=identifier))

        count = clients.count()
        if count == 1:
            client = clients.next()
            raise web.seeother(link('clientview', client['_id']))

        # redirect to the all clients page
        # with search pre-filled
        raise web.seeother(link('allclients', q=identifier))


class ClientDelete(app.page, CorpBase):
    path = '/clienthub/delete/([^/]+)'

    @authenticated
    def GET(self, pageParams, client_id, *args):
        client = Client(client_id)
        if not client._id:
            raise web.seeother(link('clienthub'))

        db.clients.docs.remove({'client_id': client._id})
        db.clients.remove({'_id': client._id})

        raise web.seeother(link('clienthub'))

class ExportClientView(app.page, CorpBase):
    path = '/clienthub/view/([^/]+)/export/'

    @authenticated
    def GET(self, pageParams, client_id, *args):
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
                issue['status_name'] = status.get('name', '')
            except:
                issue['status_name'] = status
            try:
                issue['priority_name'] = priority.get('name', '')
            except:
                issue['priority_name'] = priority

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


class ClientViewSalesForce(app.page, CorpBase):
    path = '/clienthub/view/salesforce/([^/]+)'

    @authenticated
    def GET(self, pageParams, salesforce_id, *args):
        client  = db.clients.find_one({'sf_account_id':{'$regex':'^' + salesforce_id}}) #We add three extra letters to the sfid when importing it, so relax the terms slighty
        if not client:
            raise web.seeother('/clienthub')

        client = Client(client['_id'])

        web.header('Content-type', 'text/html')
        return env.get_template('clienthub/salesforce_view.html').render(
            client=client,
        )



class ClientView(app.page, CorpBase):
    path = '/clienthub/view/([^/]+)'

    @authenticated
    def GET(self, pageParams, client_id, *args):
        client = Client(client_id)
        if not client._id:
            raise web.seeother('/clienthub')

        # show the "loading" page
        if 'loadcache' not in web.input() and not client.is_up_to_date():
            web.header('Content-Type', 'text/html')
            return env.get_template('clienthub/view_loading.html').render(
                client=client
            )
        elif 'loadcache' in web.input():
            client.load_caches()
            raise web.seeother(link('clientview', client._id))

        docs = list(db.clients.docs.find({'client_id': client._id}).sort([('updated', pymongo.DESCENDING)]))
        web.header('Content-type', 'text/html')
        return env.get_template('clienthub/view.html').render(
            client=client,
            docs=docs,
        )

class ClientDocView(app.page, CorpBase):
    path = '/clienthub/view/([^/]+)/docs/([^/]+)/([^/]+)'

    @authenticated
    def GET(self, pageParams, client_id, doc_type, doc_id, *args):
        client = Client(client_id)
        if not client._id:
            raise web.seeother(link('clienthub'))

        xgenners = crowd_api.get_users_for_group('10gen')
        xgenners.sort(key=lambda x: x['displayName'])

        if doc_id == 'new':
            doc = {'author': web.cookies()['auth_user']}
            web.header('Content-type', 'text/html')

            html = env.get_template('clienthub/docs/' + doc_type + '.html').render(
                client=client,
                doc_type=doc_type,
                doc=doc,
                xgenners=xgenners,
            )
            return htmlfill.render(html, defaults=doc, force_defaults=False)

        doc = db.clients.docs.find_one({'_id': ObjectId(doc_id), 'client_id': client._id})
        if not doc:
            raise web.seeother(link('clientview', client._id))

        tparams = {}
        # TODO: handle more than 1 attachment
        if 'attachment' in doc and doc['attachment']['content_type'].startswith('text'):
            # stick the content directly into the template
            file_id = doc['attachment']['file_id']
            fp = gridfs.GridFS(db, 'clients.uploads').get(file_id)
            tparams['attachment_content'] = fp.read()

        template = 'clienthub/docs/' + doc_type + '.html'
        if doc_type != 'chatlog':
            legacy_fields = extract_legacy_fields(template, doc)
        else:
            legacy_fields = []

        html = env.get_template(template).render(
            client=client,
            doc=doc,
            legacy_fields=legacy_fields,
            xgenners=xgenners,
            **tparams
        )
        html = htmlfill.render(html, defaults=doc, force_defaults=False)
        web.header('Content-type', 'text/html')
        return html

    def _handle_attachments(self, params):
        # find any attachments in the params (and remove
        # them from the params dict), and return a list
        # of attachments of the form:
        #
        # [{'filename': ..., 'content_type': ..., 'file_id': ...}, ...]
        #
        # file_id is a valid ID to the gridfs collection
        # stored at db.clients.uploads.files
        #
        # attachments returned should be merged into the
        # attachments list that already exists for the
        # document (if any)
        attachments = []

        attachment_keys = [k for k in params.keys() if k.startswith('attachment')]
        new_params = web.input(**dict((k, {}) for k in attachment_keys))
        for key in attachment_keys:
            # remove key from the original params.
            # this lets POST do doc.update(params)
            # and work as expected
            params.pop(key, None)

            attachment = new_params[key]

            fp_in = attachment.file
            filename = attachment.filename
            if not filename:
                continue

            content_type, encoding = mimetypes.guess_type(filename)
            if not content_type:
                # not a real MIME type, but good enough
                content_type = 'application/binary'

            storage = gridfs.GridFS(db, 'clients.uploads')
            # it's ok if filename is not unique, since
            # we only look up files by file._id
            fp_out = storage.new_file(
                filename=filename,
                content_type=content_type,
                encoding=encoding)

            chunk = fp_in.read(32768)
            while chunk != '':
                fp_out.write(chunk)
                chunk = fp_in.read(32768)

            fp_out.close()
            fp_in.close()

            attachments.append({
                'filename': filename,
                'file_id': fp_out._id,
                'content_type': content_type,
            })

        return attachments


    @authenticated
    def POST(self, pageParams, client_id, doc_type, doc_id):
        client = Client(client_id)
        if not client._id:
            raise web.seeother(link('clienthub'))

        params = web.input(author=[])

        params.pop('submit', None)
        save_and_stay = bool(params.pop('save-and-stay', False))

        unset_checkboxes = params.pop('_unset_checkbox', '')
        attachments = self._handle_attachments(params)

        if doc_id == 'new':
            doc = dict(params)
            doc['client_id'] = ObjectId(client_id)
            doc['_type'] = doc_type
            doc['created'] = datetime.datetime.utcnow()
            notify = True
        else:
            doc = db.clients.docs.find_one({'_id': ObjectId(doc_id), 'client_id': client._id})
            doc.update(params)
            notify = False

        doc['updated'] = datetime.datetime.utcnow()
        doc['web_user'] = web.cookies()['auth_user']

        # TODO: support more than 1 attachment
        if len(attachments):
            doc['attachment'] = attachments[0]

        # trim keys for empty values
        for key, value in doc.items():
            if value == '':
                del doc[key]

        # also unset any checkboxes that may
        # have been previously set
        for field_name in unset_checkboxes.split(','):
            doc.pop(field_name, None)

        doc_id = db.clients.docs.save(doc)

        if notify:
            recipients = set()
            recipients.add(client.primary_eng)
            recipients.update(client.secondary_engs)
            recipients.add(client.account_contact)

            # don't email the person who added the
            # doc or anyone who's listed as an "author"
            recipients = recipients - set(doc['author'])

            # XGEN-1047: always add certain users
            recipients.update([
                'dan@10gen.com',
                'sabina',
                'alvin',
                'spf13',
            ])

            # unless they created the doc
            recipients.discard(doc['web_user'])

            xgenners = crowd_api.get_users_for_group('10gen')
            email_by_username = dict((u['username'], u['mail']) for u in xgenners)
            name_by_username = dict((u['username'], u['displayName']) for u in xgenners)
            recipients = [email_by_username.get(r, r) for r in recipients]

            if recipients:
                subject = 'New Clienthub Doc: %s for %s' % (doc['_type'], client.name)
                body = ['Type:         %(type)s',
                        'Creator:      %(creator)s',
                        'Participants: %(participants)s',
                        'Summary:      %(summary)s',
                        '',
                        '%(link)s',]

                body = '\n'.join(body)
                body = body % {
                    'type': doc['_type'],
                    'creator': name_by_username.get(doc['web_user'], doc['web_user']),
                    'participants': ', '.join(
                        name_by_username.get(u, u) for u in doc['author'] if u != doc['web_user']),
                    'summary': doc.get('summary', ''),
                    'link': web.ctx.homedomain + link('clientdocview', client._id, doc['_type'], doc['_id'])
                }
                web.utils.sendmail('info@10gen.com', recipients, subject, body)

        if save_and_stay:
            raise web.seeother(link('clientdocview', client_id, doc['_type'], doc_id))
        else:
            raise web.seeother(link('clientview', client_id))

class ClientDocDelete(app.page, CorpBase):
    path = '/clienthub/view/([^/]+)/docs/([^/]+)/([^/]+)/delete'

    @authenticated
    def GET(self, pageParams, client_id, doc_type, doc_id, *args):
        doc_id = ObjectId(doc_id)
        doc = db.clients.docs.find_one({'_id': doc_id})
        if not doc:
            raise web.seeother(link('clientview', client_id))

        # delete attachments, if any
        if 'attachment' in doc:
            id = ObjectId(doc['attachment']['file_id'])
            db.clients.uploads.chunks.remove({'files_id': id})
            db.clients.uploads.files.remove({'_id': id})

        db.clients.docs.remove({'_id': doc_id})
        raise web.seeother(link('clientview', client_id))

class ClientForm(formencode.Schema):
    allow_extra_fields = True

    name = validators.NotEmpty()

class ClientEdit(app.page, CorpBase):
    path = '/clienthub/edit/(.+)'

    @authenticated
    def GET(self, pageParams, client_id, *args):
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
        return env.get_template('clienthub/edit.html').render(
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
    def POST(self, pageParams, client_id):
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
        _id = db.clients.save(client_doc)
        raise web.seeother(link('clientview', _id))

class ClientUploadView(app.page, CorpBase):
    path = '/clienthub/view/([^/]+)/uploads/([^/]+)/([^/]+)'

    @authenticated
    def GET(self, pageParams, client_id, file_id, filename, *args):
        try:
            file_id = ObjectId(file_id)
            fp = gridfs.GridFS(db, 'clients.uploads').get(file_id)
        except gridfs.NoFile:
            raise app.notfound()

        if fp.content_type:
            web.header('Content-Type', fp.content_type)
            if fp.content_type.startswith('application'):
                web.header('Content-Disposition', 'attachment; filename=%s' % fp.filename)
        if fp.encoding:
            web.header('Content-Encoding', fp.encoding)

        chunk = fp.read(32768)
        while chunk != '':
            yield chunk
            chunk = fp.read(32768)

class ClientCacheRefresh(app.page, CorpBase):
    path = '/clienthub/view/([^/]+)/refreshcache/([^/]+)'

    cache_key = {
        'all_groups': lambda: crowd_api.get_all_groups.expire(),
        'xgenners': lambda: crowd_api.get_users_for_group.expire('10gen'),
        'jira_groups': lambda: jira_api.getGroupsInProjectRole.expire('Customer','CS'),
        'sf_accounts': lambda: salesforce_api.get_accounts.expire(),
    }

    @authenticated
    def GET(self, pageParams, client_id, cache_types, *args):
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

class ClientContactUpdate(app.page, CorpBase):
    path = '/clienthub/view/([^/]+)/contact/([^/]+)/([^/]+)'

    @authenticated
    def GET(self, pageParams, client_id, contact_id, action, *args):
        client = Client(client_id)
        if action == 'setprimary':
            client.set_primary_contact(contact_id)
        elif action == 'unsetprimary':
            client.set_primary_contact(None)
        elif action == 'setsecondary':
            client.set_secondary_contact(contact_id)
        elif action == 'unsetsecondary':
            client.set_secondary_contact(None)
        elif action == 'addtojira':
            client.add_contact_to_jira(contact_id)
        elif action == 'removefromjira':
            # contact_id is the jira_username
            client.remove_contact_from_jira(contact_id)
        raise web.seeother(link('clientview', client._id))

class DocumentSearch(app.page, CorpBase):
    path = '/clienthub/docsearch'

    @authenticated
    def GET(self, *args):
        terms = web.input().get('search', '')
        results = None
        error = None
        clients = None

        if terms:
            try:
                output = ftsdb.command('fts', 'clients.docs', search=terms)
            except OperationFailure, of:
                error = str(of)
            else:
                results = [x['obj'] for x in output['results']]

                client_ids = set()
                for result in results:
                    client_ids.add(result['client_id'])

                clients = db.clients.find({'_id': {'$in': list(client_ids)}})
                clients = dict((c['_id'], Client()._from_db(c)) for c in clients)

                for result in results:
                    client = clients[result['client_id']]
                    result['client'] = client

        web.header('Content-Type', 'text/html')
        return env.get_template('clienthub/docsearch.html').render(
            results=results,
            clients=clients,
            terms=terms,
            error=error,
        )
