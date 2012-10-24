import web

import config
from config import env

from corplibs.webutils import link
from corplibs.authenticate import authenticated

class AdminHeartbeat(object):
    # this is called from javascript when a user
    # has a window open in 10gen.com/admin or
    # 10gen.com/clienthub -- this will prevent
    # the user's session from timing out if they
    # have an active window open.
    #
    # since the session automatically updates
    # whenever a request comes in (for IP and
    # last access time), no actual work is
    # necessary here.

    def GET(self):
        web.header('Content-Type', 'text/plain')
        return ''


class Login(object):
    def GET(self):
        return env.get_template("login.html").render()

    def POST(self):
        params = web.input()
        if 'user' in params and 'password' in params:
            res = config.auth.login(params.user, params.password)
            if res["ok"]:
                raise web.seeother(link(config.app, "client.clienthub"))
            return env.get_template("login.html").render(error=res["err"])
        else:
            return env.get_template("login.html").render(
              error="Username and Password are required")

class Logout(object):
    def GET(self):
        config.auth.logout()
        return env.get_template("login.html").render()


class ClienthubRedirector(object):

    @authenticated
    def GET(self, identifier_type, identifier):
        if identifier_type in ('jira', 'jira_group'):
            clients = config.get_db().clients.find({'jira_group': identifier})
        elif identifier_type == 'name':
            clients = config.get_db().clients.find({'name': identifier})
        else:
            # redirect to the search page
            raise web.seeother(link('client.allclients', q=identifier))

        count = clients.count()
        if count == 1:
            client = clients.next()
            raise web.seeother(link('client.clientview', client['_id']))

        # redirect to the all clients page
        # with search pre-filled
        raise web.seeother(link('client.allclients', q=identifier))


