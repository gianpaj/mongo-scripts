# -*- coding: utf-8 -*-
import os
import logging
import argparse
import sys
import web

import corplibs.integration
import corplibs.authenticate

import config

_logger = logging.getLogger(__name__)

system_urls = (
'/login', 'view.system.Login',
'/logout', 'view.system.Logout',
'/api/heartbeat', 'view.system.AdminHeartbeat',
'/link/(.+)/(.+)', 'view.system.ClienthubRedirector',
)

client_urls = (
'/', 'view.client.ClientHub',
'/all', 'view.client.AllClients',
'/view/([^/]+)', 'view.client.ClientView',
'/edit/([^/]+)', 'view.client.ClientEdit',
'/delete/([^/]+)', 'view.client.ClientDelete',
'/view/([^/]+)/refreshcache/([^/]+)', 'view.client.ClientCacheRefresh',
'/view/([^/]+)/export/', 'view.client.ExportClientView',
)

client_doc_urls = (
'/view/([^/]+)/docs/([^/]+)/([^/]+)', 'view.doc.ClientDocView',
'/view/([^/]+)/uploads/([^/]+)/([^/]+)', 'view.doc.ClientUploadView',
'/view/([^/]+)/docs/([^/]+)/([^/]+)/delete', 'view.doc.ClientDocDelete',
'/docsearch', 'view.doc.DocumentSearch',
)

client_contact_urls = (
'/view/([^/]+)/contact/([^/]+)/([^/]+)', 'view.contact.ClientContactUpdate',
)

report_urls = (
'/reports', 'view.report.ClientHubReports',
'/reports/([^/]+)/schedule', 'view.report.ClientHubScheduleReport',
'/reports/([^/]+)/view', 'view.report.ClientHubViewReport',
)

jira_urls = (
'/jira', 'view.jira.JiraTool',
'/jira/_refresh', 'view.jira.JiraRefresh',
'/jira/([^/]+)/_refresh', 'view.jira.RefreshJiraGroup',
'/jira/([^/]+)/adduser', 'view.jira.AddJiraUserToGroup',
'/jira/new', 'view.jira.NewJiraGroup',
'/jira/([^/]+)', 'view.jira.JiraGroup',
'/jira/([^/]+)/remove/([^/]+)', 'view.jira.RemoveJiraUserFromGroup',
'/jira/([^/]+)/togglecs', 'view.jira.ToggleCSJiraGroup',
'/jira/([^/]+)/delete', 'view.jira.DeleteJiraGroup'
)

api_urls = (
'/api/echo', 'view.api.ClientHubEcho',
'/api/contacts/(.+)', 'view.api.ClientHubApiContacts',
'/api/upload/(.+)/(.+)', 'view.api.ClientHubApiUpload',
)

urls = system_urls + client_urls + client_doc_urls + jira_urls
urls += report_urls + client_contact_urls + api_urls

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
    config.setup(args)

    corplibs.integration.Configure(config.get_db())
    config.setup_app(urls)
    config.app.run()
