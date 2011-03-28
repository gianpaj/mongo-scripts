# Helpers to handle connecting to JIRA and logging in using SOAP
#
# The settings for the connection / username / password are kept in settings.py

import traceback
import suds.client
import settings

class JiraConnection(object):
    """Just a wrapper around a suds client that passes through getattr.

    This should always be instantiated as a Context Manager, within a with
    statement.
    """
    def __init__(self):
        """On init make a connection to JIRA and login.
        """
        try:
            self.__client = suds.client.Client(settings.jira_soap_url)
            self.__auth = self.__client.service.login(settings.jira_username, settings.jira_password)
        except:
            self.__client = None
            self.__auth = None

    @property
    def auth(self):
        """Get auth object for use in other calls to JIRA service.
        """
        return self.__auth

    def __getattr__(self, method):
        """Pass through __getattr__s to underlying client.
        """
        if self.__client is None:
            return None
        return getattr(self.__client, method)

    def __enter__(self):
        """Support for the context manager protocol.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support for the context manager protocol.

        Log out of jira. Suppress any exceptions.
        """
        if self.__client is not None:
            self.__client.service.logout(self.__auth)

        if exc_type:
            print "JIRA operation failed:"
            traceback.print_exception(exc_type, exc_val, exc_tb)
            print ""

        return True

