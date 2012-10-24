import web
from corplibs.authenticate import authenticated

class ClientContactUpdate(object):

    @authenticated
    def GET(self, client_id, contact_id, action):
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

