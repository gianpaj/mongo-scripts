import urllib
import pymongo

import web
app = web.config.app
db = web.config.wwwdb

import settings
from commonweb.util.integration import SafeCacheSet, CacheLogic
from commonweb.external import crowd
from commonweb.external import jira
from commonweb.external import salesforce


def link(controller, *args, **kwargs):
    # generate and return a URL for the given controller
    # with the given args substituted for placeholders,
    # and any kwargs set as a query string. raises
    # ValueError if the number of arguments does not
    # match the number of palceholders in the controller's
    # URL path, or if the controller cannot be found.
    # "controller" is the name (case-insensitive) of the
    # controller class (app.page sublcass), not a
    # reference to the controller class object
    app = web.config.app
    split_path = list(app._link_map.get(controller.lower(), None))
    if not split_path:
        raise ValueError('unknown controller: %s' % controller)

    args_i = 0
    for i in xrange(len(split_path)):
        part = split_path[i]
        if part is None:
            split_path[i] = args[args_i]
            args_i += 1

    if len(args) != args_i:
        raise ValueError('wrong number of arguments for controller: %s' % controller)

    url = u'/'.join(map(unicode, split_path))
    if kwargs:
        qstring = dict((k, urllib.quote(v)) for k, v in kwargs.iteritems())
        url += '?' + urllib.urlencode(qstring)
    return url



def cache_db():
    return pymongo.connection.Connection('localhost', 27017).clienthub_aux

safe_cache = SafeCacheSet(CacheLogic(cache_db()), cache_db().circuitbreaker)

class JiraAPI(jira.JiraAPI):
    cache_db = staticmethod(cache_db)

class CrowdAPI(crowd.CrowdAPI):
    cache_db = staticmethod(cache_db)

class SalesforceApi(salesforce.SalesforceAPI):
    cache_db = staticmethod(cache_db)

jira_api = JiraAPI(settings.jira_username, settings.jira_password)

salesforce_api = SalesforceApi(settings.salesforce['username'],
                               settings.salesforce['password'],
                               settings.salesforce['security_token'])

crowd_api = CrowdAPI(settings.crowdAppUser, settings.crowdAppPassword)
