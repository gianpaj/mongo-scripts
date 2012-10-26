# -*- coding: utf-8 -*-
import os
import yaml
import web
import jinja2
import time
import pymongo
from pymongo import Connection

import corplibs.jira_suds
import corplibs.xgencrowd
import corplibs.authenticate
import corplibs.webutils

import logging.config
import logging.handlers

here = os.path.dirname(__file__)

_loader = jinja2.FileSystemLoader(os.path.join(here,"templates"))
env = jinja2.Environment(loader=_loader)


# Local storage for environment specific config
_config = None

# Shared state of application environment
environment ={}

def link(*args, **nargs):
    return corplibs.webutils.link(environment['app'], *args, **nargs)

def page_is(*args, **nargs):
    return corplibs.webutils.page_is(environment['app'], web.ctx.path,
                                     *args, **nargs)

def current_user():
    try:
        return web.webapi.cookies()["auth_user"]
    except KeyError:
        return ""

def setup(args, urls):
    global _config

    config_file = file(os.path.join(here, 'config/config.yml'), 'r')
    _config = yaml.load(config_file)[args['environment']]
    environment['setup_time'] = time.time()
    logging.config.fileConfig(os.path.join(here, _config['logging_config']))

    crowd = _config["crowd"]
    jira = _config["jira"]
    db_conf = _config["db"]
    auxdb_conf = _config["aux_db"]
    ftsdb_conf = _config["fts_db"]

    db = pymongo.database.Database(Connection(db_conf['host'], safe=True), 
                                   db_conf['db_name'])
    auxdb = pymongo.database.Database(Connection(auxdb_conf['host'], safe=True),
                                      auxdb_conf['db_name'])
    ftsdb = pymongo.database.Database(Connection(ftsdb_conf['host'], safe=True),
                                      ftsdb_conf['db_name'])
    environment['ftsdb'] = ftsdb
    environment['auxdb'] = auxdb
    environment['db'] = db

    auth = corplibs.authenticate.Configure(crowd['user'], crowd['password'])
    environment['auth'] = auth

    corplibs.jira_suds.Configure(jira['user'], jira['password'])
    corplibs.xgencrowd.Configure(crowd['user'], crowd['password'])
    corplibs.integration.Configure(db)

    env.globals.update(
        web_ctx=web.ctx,
        link=link,
        page_is = page_is,
        current_user = current_user, )

    app = web.application(urls)
    environment['app'] = app
    return app

