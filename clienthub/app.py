# -*- coding: utf-8 -*-
import os
import site

root_dir = os.path.abspath(os.path.dirname(__file__))
site.addsitedir(root_dir)
site.addsitedir(os.path.join(root_dir, "venv/lib/python2.7/site-packages/"))

import logging
import argparse
import sys
import web

import config

import filters
_logger = logging.getLogger(__name__)

system_urls = (
'/clienthub/login', 'view.system.Login',
'/clienthub/logout', 'view.system.Logout',
'/clienthub/api/heartbeat', 'view.system.AdminHeartbeat',
'/clienthub/link/(.+)/(.+)', 'view.system.ClienthubRedirector',
)

client_urls = (
'/clienthub/', 'view.client.ClientHub',
'/clienthub/all', 'view.client.AllClients',
'/clienthub/view/([^/]+)', 'view.client.ClientView',
'/clienthub/edit/([^/]+)', 'view.client.ClientEdit',
'/clienthub/delete/([^/]+)', 'view.client.ClientDelete',
'/clienthub/view/([^/]+)/refreshcache/([^/]+)', 'view.client.ClientCacheRefresh',
'/clienthub/view/([^/]+)/export/', 'view.client.ExportClientView',
)

client_doc_urls = (
'/clienthub/view/([^/]+)/docs/([^/]+)/([^/]+)', 'view.doc.ClientDocView',
'/clienthub/view/([^/]+)/uploads/([^/]+)/([^/]+)', 'view.doc.ClientUploadView',
'/clienthub/view/([^/]+)/docs/([^/]+)/([^/]+)/delete', 'view.doc.ClientDocDelete',
'/clienthub/docsearch', 'view.doc.DocumentSearch',
)

client_contact_urls = (
'/clienthub/view/([^/]+)/contact/([^/]+)/([^/]+)', 'view.contact.ClientContactUpdate',
)

report_urls = (
'/clienthub/reports', 'view.report.ClientHubReports',
'/clienthub/reports/([^/]+)/schedule', 'view.report.ClientHubScheduleReport',
'/clienthub/reports/([^/]+)/view', 'view.report.ClientHubViewReport',
)

jira_urls = (
'/clienthub/jira', 'view.jira.JiraTool',
'/clienthub/jira/_refresh', 'view.jira.JiraRefresh',
'/clienthub/jira/([^/]+)/_refresh', 'view.jira.RefreshJiraGroup',
'/clienthub/jira/([^/]+)/adduser', 'view.jira.AddJiraUserToGroup',
'/clienthub/jira/new', 'view.jira.NewJiraGroup',
'/clienthub/jira/([^/]+)', 'view.jira.JiraGroup',
'/clienthub/jira/([^/]+)/remove/([^/]+)', 'view.jira.RemoveJiraUserFromGroup',
'/clienthub/jira/([^/]+)/togglecs', 'view.jira.ToggleCSJiraGroup',
'/clienthub/jira/([^/]+)/delete', 'view.jira.DeleteJiraGroup'
)

urls = system_urls + client_urls + client_doc_urls + jira_urls
urls += report_urls + client_contact_urls

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=
                                     "The Clienthub Web application.")
    parser.add_argument("-e", "--env", dest="environment", 
                        help="set environment.", 
                        choices=['local', 'dev', 'test', 'prod'], 
                        default='local')

    parser.add_argument("-p", "--port", type=int,
                        dest="port", help="port to listen on")
    args = parser.parse_args()
    args = vars(args)
    app = config.setup(args, urls)
    app.run()
else:
    args = {"environment": "local"}
    application = config.setup(args, urls)
    application = application.wsgifunc()
