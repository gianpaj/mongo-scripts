# -*- coding: utf-8 -*-
import os
import yaml
import web
import jinja2
import pymongo
from pymongo import Connection
import corplibs.authenticate
from corplibs.webutils import link
from corplibs.webutils import page_is
import inspect
import logging.config

here = os.path.dirname(__file__)
env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(here, "templates")))

auth = None

environment = None
app = None
auxdb = None

_config = None
_ftsdb = None
_db = None


def setup(args):
    global environment
    global auth
    global _config
    global _ftsdb
    global _db
    global auxdb
    environment = args['environment']
    _config = yaml.load(file('config/config.yml', 'r'))[args['environment']]

    _ftsdb = pymongo.database.Database(Connection(_config['fts_db']['host'],
                                    safe=True), _config['fts_db']['db_name'])
    auxdb = pymongo.database.Database(Connection(_config['aux_db']['host'],
                                    safe=True), _config['aux_db']['db_name'])
    _db = pymongo.database.Database(Connection(_config['db']['host'],
                                    safe=True), _config['db']['db_name'])
    crowd = _config["crowd"]
    auth = corplibs.authenticate.Configure(crowd['user'], crowd['password'])
    jira = _config["jira"]
    corplibs.jira_suds.Configure(jira['user'], jira['password'])
    corplibs.xgencrowd.Configure(crowd['user'], crowd['password'])

def setup_app(urls):
    global app
    app = web.application(urls)
    def link2(*arg, **nargs):
        return link(app, *arg, **nargs)
    def page_is2(*args, **nargs):
        return page_is(app, web.ctx.path, *args, **nargs)

    def current_user():
        try:
            return web.webapi.cookies()["auth_user"]
        except KeyError:
            return ""


    env.globals.update(
        web_ctx=web.ctx,
        link=link2,
        page_is = page_is2,
        current_user = current_user, )

def get_db():
    return _db

def get_ftsdb():
    return _ftsdb

def get_crowd_credentials():
    return _config["crowd"]

logging.config.fileConfig('config/logging.conf')
