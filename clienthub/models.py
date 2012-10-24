from functools import wraps
from datetime import datetime
import urllib
import urllib2
try:
    import json
except:
    import simplejson as json

from bson.objectid import ObjectId
import web

import config

from corplibs import xgencrowd
from corplibs import jira_suds
from corplibs import salesforce
from corplibs.integration import makesafe, call_safely

salesforce_api = salesforce.SalesforceAPI()
jira_api = jira_suds.JiraAPI()
crowd_api = xgencrowd.CrowdAPI()

@call_safely
@makesafe(default=False, cache_ttl=86400)
def client_has_mms(jira_group):
    if not jira_group:
        return False
    try:
        url = 'https://mms.10gen.com/customer/hasSumthin?id=%s,425989&code=al-2343-jaf8-23'
        url = url % urllib.quote(jira_group)
        resp = urllib2.urlopen(url)
        body = resp.read()
        return json.loads(body)['has']
    except:
        # log and return False
        app.log_current_exception()
    return False

class Client(object):

    # these are the fields we will expect on the client database
    # entry, and set attributes on the client as such. if the
    # field does not exist on the entry, an attribute with
    # value None will be created
    #
    # XXX: if you change this, you must coordinate with Ryan
    # Nitz, since MMS uses the clients collection (read-only)
    # to display account contact, and engineering contacts
    fields = ('_id', 'name', 'account_contact', 'primary_eng', 'secondary_engs',
              'jira_group', 'sf_account_id', 'sf_account_name', 'updated',
              'checkin_tickets', 'account_contact_email', 'associated_jira_groups')

    # field defaults: only used when a Client is created with
    # is_new=True; not necessary to define all fields here,
    # if they are not defined they default to None
    field_defaults = {
        'checkin_tickets': [],
        'secondary_engs': [],
        'associated_jira_groups': [],
    }

    # service methods are automatically generated from this
    # description. a method with the name "get_<whatever>" is
    # created for each <whatever> in this dict, which calls
    # the given method with args, kwargs, and kwargs literals
    # as specified. args and kwargs are specified as fields of
    # self, and kwargs_literals is a dictionary of key-value
    # pairs which override any kwarg with the same name specified
    # in kwarg_names. format of the call spec is:
    #
    #    (func_or_method, arg_names, kwarg_names, kwarg_literals)
    #
    # this specification also serves to power the helper functions
    # get_expiry(), expire(), and others.
    service_methods = {
        'jira_cases': (jira_api.get_issues_related_to_group, ['jira_group'], [], {'limit': 10}),
        'jira_users': (jira_api.getGroup, ['jira_group']),

        # 'all_groups': (crowd_api.get_all_groups,),
        # 'xgenners': (crowd_api.get_users_for_group, [], [], {'group_name': '10gen'}),
        # 'sf_accounts': (salesforce_api.get_accounts,),

        'sf_account': (salesforce_api.get_account, ['sf_account_id']),
        'sf_contracts': (salesforce_api.get_active_support_contracts, ['sf_account_id']),
        'sf_contacts': (salesforce_api.get_account_contacts, ['sf_account_id']),
        'sf_services': (salesforce_api.get_paid_services, ['sf_account_id']),
    }

    # some expiries need extra work done afterwards to update
    # the Client object; if so, indicate that here (dict
    # value is the name of the method to call; method should
    # have no arguments. these methods should return True if
    # the client needs to be saved, or False (or None) if not
    expire_helpers = {
        'sf_account': 'update_account_contact',
    }

    # operate on logical keys that are composed of
    # several underlying service method calls
    key_map = {
        'contacts': ('jira_users', 'sf_contacts'),
    }

    def __init__(self, id=None, is_new=False):
        for name, args in self.service_methods.iteritems():
            funcname = 'get_' + name
            self.__make_call(funcname, *args)

        for f in self.fields:
            setattr(self, f, None)

        self.is_new = is_new
        if self.is_new:
            for f, default in self.field_defaults.items():
                setattr(self, f, default)

        if id not in (None, 'new', 'None'):
            record = config.get_db().clients.find_one({'_id': ObjectId(id)})
            if record is None:
                return
            self._from_db(record)

    def _from_db(self, db_record):
        for f in self.fields:
            setattr(self, f, db_record.get(f, None))
        return self

    def _fields_dict(self):
        out = {}
        for field in self.fields:
            value = getattr(self, field, None)
            if value is None:
                continue
            out[field] = value
        return out

    def __call_args(self, arg_names=[], kwarg_names=[], kwarg_literals={}):
        args = []
        for name in arg_names:
            args.append(getattr(self, name))
        kwargs = {}
        for name in kwarg_names:
            kwargs[name] = getattr(self, name)
        kwargs.update(kwarg_literals)
        return args, kwargs

    def __make_call(self, name, ip_func, arg_names=[], kwarg_names=[], kwarg_literals={}):
        # for each service method, define a function
        # service_method(), which calls the service
        # method with the given arguments.
        def innerfunc():
            args, kwargs = self.__call_args(arg_names, kwarg_names, kwarg_literals)
            return ip_func(*args, **kwargs)
        innerfunc.__name__ = name
        setattr(self, name, innerfunc)

    @property
    def has_mms(self):
        return client_has_mms(self.jira_group)

    @property
    def associated_jira_group_names(self):
        return [g['name'] for g in self.associated_jira_groups]

    @property
    def all_jira_groups(self):
        return [self.jira_group] + self.associated_jira_group_names

    def get_expiry(self, key, return_if_expired=True):
        if key in self.key_map:
            return self.get_min_expiry(self.key_map[key])

        spec = self.service_methods[key]
        callable = self.service_methods[key][0]
        args, kwargs = self.__call_args(*spec[1:])
        kwargs['return_if_expired'] = return_if_expired
        return callable.get_expiry(*args, **kwargs)

    def get_min_expiry(self, keys):
        expiries = map(self.get_expiry, keys)
        expiries = [e for e in expiries if e is not None]
        if expiries:
            return min(expiries)
        return None

    def expire(self, key):
        if key in self.key_map:
            map(self.expire, self.key_map[key])

        if key not in self.service_methods:
            return

        spec = self.service_methods[key]
        callable = spec[0]
        args, kwargs = self.__call_args(*spec[1:])
        callable.expire(*args, **kwargs)

        if key in self.expire_helpers:
            helper_name = self.expire_helpers[key]
            helper = getattr(self, helper_name, lambda self: None)
            if helper():
                config.get_db().clients.save(self._fields_dict())

    def update_account_contact(self):
        needs_save = False
        sf_account = self.get_sf_account()
        if sf_account:
            owner_email = sf_account['owner_email']

            # also expire the get_user_by_email, since this
            # is sometimes off or wrong for new salesfolks
            crowd_api.get_user_by_email.expire(owner_email)
            crowd_user = crowd_api.get_user_by_email(owner_email) or {}

            jira_username = crowd_user.get('username', owner_email)
            if self.account_contact != jira_username:
                needs_save = True
                self.account_contact = jira_username

            if self.sf_account_name != sf_account['name']:
                needs_save = True
                self.sf_account_name = sf_account['name']

        return needs_save

    def is_up_to_date(self):
        # False if any cached value exists but is
        # expired or if no cached values exist;
        # True otherwise
        now = datetime.utcnow()
        any_cached = False
        for key in self.service_methods:
            expiry = self.get_expiry(key, return_if_expired=False)
            if expiry and expiry < now:
                return False
            any_cached = any_cached or (expiry is not None)
        return any_cached

    def get_contacts(self):
        # get all contacts from salesforce and jira,
        # and merge the lists together.
        sf_contacts = self.get_sf_contacts()
        jira_contacts = self.get_jira_users()

        if not sf_contacts:
            sf_contacts = []
        if not jira_contacts:
            jira_contacts = []

        index = {}
        for user in jira_contacts:
            index[user['email'].strip().lower()] = user

        out = []
        for user in sf_contacts:
            user['is_sfdc'] = True
            merge = index.pop(user['email'].strip().lower(), None)
            if merge:
                user['jira_username'] = merge['name']
                user['is_jira'] = True
            else:
                user['is_jira'] = False
            out.append(user)

        for user in index.itervalues():
            out.append({
                'name': user['fullname'],
                'jira_username': user['name'],
                'email': user['email'],
                'is_jira': True,
                'is_sfdc': False,
            })

        out.sort(key=lambda x: x['name'].lower())
        return out

    def get_address(self):
        a = self.get_sf_account()
        if not a:
            return None
        address = (a.get('street',''), '%s, %s %s' % (a.get('city',''), a.get('state',''), a.get('zip','')), a.get('country',''))
        address = '\n'.join(address)
        return address.strip()

    def load_caches(self):
        # call all service methods to prime
        # the cache; any that are already
        # cached and not expired will return
        # from the cache immediately
        for key in self.service_methods:
            funcname = 'get_' + key
            getattr(self, funcname)()

        # also update some locally-cached
        # information, to make sure it is
        # consistent
        needs_save = self.update_account_contact()

        if needs_save:
            config.get_db().clients.save(self._fields_dict())


    def expire_all(self):
        # call expire() on all service methods
        for key in self.service_methods:
            self.expire(key)

    def get_jira_cases_with_extras(self, limit=10, jira_cases=None):
        status_map = jira_api.getStatusMap()
        priority_map = jira_api.getPriorityMap()
        if not jira_cases:
            jira_cases = self.get_jira_cases()

        # also get checkin tickets
        for ticket in self.checkin_tickets:
            jira_cases.append(jira_api.get_issue(ticket['key']))

        users = {}
        for case in jira_cases:
            if not case['assignee']:
                case['assignee'] = ''
                case['assignee_fullname'] = ''
                continue
            if case['assignee'] not in users:
                users[case['assignee']] = jira_api.getUser(case['assignee'])
            user = users[case['assignee']]
            if user:
                case['assignee_fullname'] = user['fullname']
            else:
                case['assignee_fullname'] = case['assignee']
            case['status'] = status_map[case['status']]
            case['priority'] = priority_map[case['priority']]

        jira_cases.sort(key=lambda ticket: ticket['updated'], reverse=True)
        jira_cases = jira_cases[:limit]

        return jira_cases

    def display_names(self, usernames):
        if usernames is None:
            usernames = [self.primary_eng, self.account_contact]
            usernames.extend(self.secondary_engs or [])
            usernames = [username for username in usernames if username is not None]
        elif isinstance(usernames, basestring):
            usernames = [usernames]
        out = []
        xgenner_map = {}
        for xgenner in crowd_api.get_users_for_group('10gen'):
            xgenner_map[xgenner['username']] = xgenner
        for eng in usernames:
            out.append(xgenner_map.get(eng, {}).get('displayName', eng))
        return ', '.join(out)

    def display_engineering_contact(self):
        if not self.primary_eng:
            return ''

        return self.display_names([self.primary_eng])

    def display_secondary_engineers(self):
        if not self.secondary_engs:
            return ''

        return self.display_names(self.secondary_engs)

    def display_account_contact(self):
        if not self.account_contact:
            return ''

        return self.display_names([self.account_contact])

    def contact_is_primary(self, contact_id):
        if contact_id and self.sf_account_id:
            acct = self.get_sf_account()
            return contact_id == acct['primary_support_contact_id']
        return False

    def contact_is_secondary(self, contact_id):
        if contact_id and self.sf_account_id:
            acct = self.get_sf_account()
            return contact_id == acct['secondary_support_contact_id']
        return False

    def set_primary_contact(self, contact_id):
        if self.contact_is_secondary(contact_id):
            self.set_secondary_contact(None)
        succeeded = salesforce_api.set_primary_contact(self.sf_account_id, contact_id)
        if succeeded:
            self.expire('sf_account')

    def set_secondary_contact(self, contact_id):
        if self.contact_is_primary(contact_id):
            self.set_primary_contact(None)
        succeeded = salesforce_api.set_secondary_contact(self.sf_account_id, contact_id)
        if succeeded:
            self.expire('sf_account')

    def add_contact_to_jira(self, contact_id):
        if not self.jira_group:
            return

        contact = None
        for c in self.get_sf_contacts():
            if c['id'] == contact_id:
                contact = c
                break
        if not contact_id:
            return

        # does a JIRA user exist?
        crowd_user = crowd_api.get_user_by_email(contact['email'])
        if crowd_user:
            jira_user = jira_api.getUser(crowd_user['username'])
        else:
            jira_user = jira_api.create_user(
                username=contact['email'],
                realname=contact['name'],
                email=contact['email']
            )
            crowd_api.get_user_by_email.expire(contact['email'])

        jira_api.add_user_to_group(self.jira_group, jira_user)
        self.expire('contacts')

    def remove_contact_from_jira(self, jira_username):
        jira_api.remove_user_from_group(self.jira_group, jira_username)
        self.expire('contacts')

    def is_my_client(self, xgen_username):
        usernames = [self.primary_eng, self.account_contact]
        usernames.extend(self.secondary_engs or [])
        return xgen_username in usernames
