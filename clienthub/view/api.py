from datetime import datetime
from functools import wraps
import json
from urllib import unquote
import re
import pytz

import web
app = web.config.app
env = web.config.env
db = web.config.db

from xgen.clienthub.models import Client
from xgen.admin.auth import requires_digest_auth
from xgen.admin.crowd import CrowdAPI
from xgen.webutils import link

crowd_api = CrowdAPI()

def notfound(message=None):
    if message is None:
        message = 'client not found'
    message = json.dumps(dict(error=True, message=message))
    return web.HTTPError("404 Not Found", {}, message)

def error(message):
    message = json.dumps(dict(error=True, message=message))
    return web.HTTPError("400 Bad Request", {}, message)

def return_json(func):
    @wraps(func)
    def inner(*args, **kwargs):
        out = func(*args, **kwargs)
        if type(out) in (dict, list):
            out = json.dumps(out)
            web.header('Content-Type', 'application/json')
            web.header('Content-Length', str(len(out) + 1))
            return out + '\n'
        return out
    return inner


class ClientHubEcho(app.page):
    path = '/clienthub/api/echo'

    @requires_digest_auth(realm='clienthub')
    def GET(self):
        web.header('Content-Type', 'text/plain')
        return web.data()

    @requires_digest_auth(realm='clienthub')
    def POST(self):
        web.header('Content-Type', 'text/plain')
        return web.data()

class ClientHubApiContacts(app.page):
    path = '/clienthub/api/contacts/(.+)'

    @requires_digest_auth(realm='clienthub')
    @return_json
    def GET(self, client_name):
        client_name_re = re.compile(client_name, re.IGNORECASE)
        client = db.clients.find_one({'name': client_name_re})
        if not client:
            raise notfound()

        client = Client()._from_db(client)

        params = web.input()
        if 'email' in params:
            return self.check_contact(client, params.get('email'))

        return self.contacts(client)


    def check_contact(self, client, email):
        for contact in client.get_contacts():
            if not contact.get('jira_username'):
                continue

            if email == contact['email']:
                return [{
                    'email': contact['email'],
                    'name': contact['name'],
                    'jira_username': contact.get('jira_username'),
                    'is_xgen': False,
                    'is_primary': False,
                    'is_jira': contact['is_jira'],
                    'is_sfdc': contact['is_sfdc'],
                    'role': 'client',
                }]

        xgenner_map = {}
        for xgenner in crowd_api.get_users_for_group('10gen'):
            xgenner_map[xgenner['username']] = xgenner

        xgenners = []
        xgenners.append(client.account_contact)
        xgenners.append(client.primary_eng)
        xgenners.extend(client.secondary_engs)

        for xgenner in xgenners:
            data = xgenner_map[xgenner]
            if data['mail'] == email:
                return [{
                    'email': data['mail'],
                    'name': data['displayName'],
                    'jira_username': xgenner,
                    'is_xgen': True,
                    'is_primary': xgenner in (client.account_contact, client.primary_eng),
                    'is_jira': False,
                    'is_sfdc': False,
                    'role': xgenner == client.account_contact and 'sales' or 'engineering'
                }]

        return []


    def contacts(self, client):
        xgenner_map = {}
        for xgenner in crowd_api.get_users_for_group('10gen'):
            xgenner_map[xgenner['username']] = xgenner

        contacts = []

        if client.account_contact:
            contacts.append({
                'email': xgenner_map[client.account_contact]['mail'],
                'name': xgenner_map[client.account_contact]['displayName'],
                'jira_username': client.account_contact,
                'is_xgen': True,
                'is_primary': True,
                'is_jira': False,
                'is_sfdc': False,
                'role': 'sales',
            })

        if client.primary_eng:
            contacts.append({
                'email': xgenner_map[client.primary_eng]['mail'],
                'name': xgenner_map[client.primary_eng]['displayName'],
                'jira_username': client.primary_eng,
                'is_xgen': True,
                'is_primary': True,
                'is_jira': False,
                'is_sfdc': False,
                'role': 'engineering',
            })

        for engineer in client.secondary_engs:
            contacts.append({
                'email': xgenner_map[engineer]['mail'],
                'name': xgenner_map[engineer]['displayName'],
                'jira_username': engineer,
                'is_xgen': True,
                'is_primary': False,
                'is_jira': False,
                'is_sfdc': False,
                'role': 'engineering',
            })

        for contact in client.get_contacts():
            # for now, only include JIRA contacts
            if 'jira_username' not in contact or not contact['jira_username']:
                continue
            contacts.append({
                'email': contact['email'],
                'name': contact['name'],
                'jira_username': contact['jira_username'],
                'is_xgen': False,
                'is_primary': False,
                'is_jira': contact['is_jira'],
                'is_sfdc': contact['is_sfdc'],
                'role': 'client',
            })

        return contacts

def decode_dollar_date(obj):
    # used as an object_hook for json.load/json.loads
    # decodes {"$date": ...} into a datetime.datetime
    # object (in UTC); timestamp is interpreted as
    # milliseconds UTC, per "strict" JSON mode:
    # http://www.mongodb.org/display/DOCS/Mongo+Extended+JSON
    if type(obj) != dict or len(obj) != 1 or '$date' not in obj:
        return obj
    if type(obj['$date']) not in (int, long, float):
        raise ValueError('expected number value for $date')
    return datetime.fromtimestamp(obj['$date'] / 1000.0, pytz.utc)

class ClientHubApiUpload(app.page):
    path = '/clienthub/api/upload/(.+)/(.+)'

    @requires_digest_auth(realm='clienthub')
    @return_json
    def POST(self, upload_type, client_name):
        if upload_type not in ('chatlog', ):
            raise notfound('Unknown upload type "%s"' % upload_type)

        client = db.clients.find_one({'name': client_name})
        if not client:
            raise notfound()

        client = Client()._from_db(client)

        post_body = web.data()
        if re.search(r'%[0-9A-Fa-f]{2}', post_body):
            post_body = unquote(post_body)

        # validate the JSON "schema"
        try:
            body = json.loads(post_body, object_hook=decode_dollar_date)
        except:
            app.log_current_exception()
            raise error('could not decode JSON')

        try:
            assert type(body) == list
            for i, message in enumerate(body):
                assert len(message) == 3, "expected 3 elements in element %d" % i

                assert 'content' in message, "key 'content' missing in element %d" % i
                assert type(message['content']) in (str, unicode), "key 'content' is %d not str in element %d" % (type(message['content']), i)

                assert 'user' in message, "key 'user' missing in element %d" % i
                assert type(message['user']) in (str, unicode), "key 'user' is %d not str in element %d" % (type(message['user']), i)

                assert 'time' in message, "key 'time' missing in element %d" % i
                assert type(message['time']) == datetime, "key 'time' is %d not datetime in element %d" % (type(message['time']), i)
        except AssertionError, ae:
            app.log_current_exception()
            raise error('invalid chatlog: %s' % ae)

        # sort the chat log, probably not necessary
        body.sort(key=lambda x: x['time'])
        start_time = body[0]['time']
        end_time = body[-1]['time']

        # convert to US/Eastern
        start_time = start_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('US/Eastern'))
        end_time = end_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('US/Eastern'))

        if start_time.date() == end_time.date():
            time_str = '%s - %s' % (start_time.strftime('%Y-%m-%d %H:%M'), end_time.strftime('%H:%M %Z'))
        else:
            time_str = '%s - %s' % (start_time.strftime('%Y-%m-%d %H:%M'), end_time.strftime('%Y-%m-%d %H:%M %Z'))

        doc = {}
        doc['client_id'] = client._id
        doc['_type'] = 'chatlog'
        doc['created'] = datetime.utcnow()
        doc['updated'] = doc['created']
        doc['author'] = 'api'
        doc['web_user'] = 'api'
        doc['summary'] = 'Chat Log: %s' % time_str
        doc['chat'] = body
        chat_id = db.clients.docs.save(doc)

        url = link('clientdocview', client._id, 'chatlog', chat_id)
        url = web.ctx.homedomain + url
        return {'error': False, 'url': url}

