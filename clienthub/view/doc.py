import logging
import web
import datetime
import mimetypes

import gridfs

from BeautifulSoup import BeautifulSoup

from corplibs.authenticate import authenticated
from models import Client

from corplibs.xgencrowd import CrowdAPI
crowd_api = CrowdAPI()

import formencode
from formencode import validators
from formencode import htmlfill

import pymongo
from bson.objectid import ObjectId
from pymongo.errors import OperationFailure

import config
from config import env
from config import link
from config import environment

_logger = logging.getLogger(__name__)

def extract_legacy_fields(form_template, doc):
    # we have to render the template here, since the
    # doc template may use macros; this will be safer
    # than trying to manually parse the macros out.
    html = env.get_template(form_template).render(
        client=Client(),
        doc={},
        legacy_fields={},
    )

    non_legacy_fields = set()

    soup = BeautifulSoup(html)
    for field in soup.findAll(['input', 'select', 'textarea']):
        name = field.get('name', None)
        if name:
            non_legacy_fields.add(name)

    internal_fields = set(['_id', 'client_id', '_type', 'web_user', '_legacy'])

    unused_fields = {}
    for field_name in doc.keys():
        if field_name not in non_legacy_fields and field_name not in internal_fields:
            unused_fields[field_name] = doc.pop(field_name)

    return unused_fields


class ClientDocView(object):

    @authenticated
    def GET(self, client_id, doc_type, doc_id):
        client = Client(client_id)
        if not client._id:
            raise web.seeother(link('client.clienthub'))

        xgenners = crowd_api.get_users_for_group('10gen')
        xgenners.sort(key=lambda x: x['displayName'])

        if doc_type == "quarterly": #moved quarterly checkins to be clientcheckins - old bookmarks and the like.
            doc_type = "clientcheckin"

        if doc_id == 'new':
            doc = {'author': web.cookies()['auth_user']}
            web.header('Content-type', 'text/html')

            html = env.get_template('docs/' + doc_type + '.html').render(
                client=client,
                doc_type=doc_type,
                doc=doc,
                xgenners=xgenners,
            )
            return htmlfill.render(html, defaults=doc, force_defaults=False)

        doc = environment['db'].clients.docs.find_one({'_id': ObjectId(doc_id), 'client_id': client._id})
        if not doc:
            raise web.seeother(link('client.clientview', client._id))

        tparams = {}
        # TODO: handle more than 1 attachment
        if 'attachment' in doc and doc['attachment']['content_type'].startswith('text'):
            # stick the content directly into the template
            file_id = doc['attachment']['file_id']
            fp = gridfs.GridFS(environment['db'], 'clients.uploads').get(file_id)
            tparams['attachment_content'] = fp.read()

        template = 'docs/' + doc_type + '.html'
        if doc_type != 'chatlog':
            legacy_fields = extract_legacy_fields(template, doc)
        else:
            legacy_fields = []

        html = env.get_template(template).render(
            client=client,
            doc=doc,
            legacy_fields=legacy_fields,
            xgenners=xgenners,
            **tparams
        )
        html = htmlfill.render(html, defaults=doc, force_defaults=False)
        web.header('Content-type', 'text/html')
        return html

    def _handle_attachments(self, params):
        # find any attachments in the params (and remove
        # them from the params dict), and return a list
        # of attachments of the form:
        #
        # [{'filename': ..., 'content_type': ..., 'file_id': ...}, ...]
        #
        # file_id is a valid ID to the gridfs collection
        # stored at db.clients.uploads.files
        #
        # attachments returned should be merged into the
        # attachments list that already exists for the
        # document (if any)
        attachments = []

        attachment_keys = [k for k in params.keys() if k.startswith('attachment')]
        new_params = web.input(**dict((k, {}) for k in attachment_keys))
        for key in attachment_keys:
            # remove key from the original params.
            # this lets POST do doc.update(params)
            # and work as expected
            params.pop(key, None)

            attachment = new_params[key]

            fp_in = attachment.file
            filename = attachment.filename
            if not filename:
                continue

            content_type, encoding = mimetypes.guess_type(filename)
            if not content_type:
                # not a real MIME type, but good enough
                content_type = 'application/binary'

            storage = gridfs.GridFS(environment['db'], 'clients.uploads')
            # it's ok if filename is not unique, since
            # we only look up files by file._id
            fp_out = storage.new_file(
                filename=filename,
                content_type=content_type,
                encoding=encoding)

            chunk = fp_in.read(32768)
            while chunk != '':
                fp_out.write(chunk)
                chunk = fp_in.read(32768)

            fp_out.close()
            fp_in.close()

            attachments.append({
                'filename': filename,
                'file_id': fp_out._id,
                'content_type': content_type,
            })

        return attachments


    @authenticated
    def POST(self, client_id, doc_type, doc_id):
        client = Client(client_id)
        if not client._id:
            raise web.seeother(link('client.clienthub'))

        params = web.input(author=[])

        params.pop('submit', None)
        save_and_stay = bool(params.pop('save-and-stay', False))

        unset_checkboxes = params.pop('_unset_checkbox', '')
        attachments = self._handle_attachments(params)

        if doc_id == 'new':
            doc = dict(params)
            doc['client_id'] = ObjectId(client_id)
            doc['_type'] = doc_type
            doc['created'] = datetime.datetime.utcnow()
            notify = True
        else:
            doc = environment['db'].clients.docs.find_one({'_id': ObjectId(doc_id), 'client_id': client._id})
            doc.update(params)
            notify = False

        doc['updated'] = datetime.datetime.utcnow()
        doc['web_user'] = web.cookies()['auth_user']

        # TODO: support more than 1 attachment
        if len(attachments):
            doc['attachment'] = attachments[0]

        # trim keys for empty values
        for key, value in doc.items():
            if value == '':
                del doc[key]

        # also unset any checkboxes that may
        # have been previously set
        for field_name in unset_checkboxes.split(','):
            doc.pop(field_name, None)

        doc_id = environment['db'].clients.docs.save(doc)

        if notify:
            recipients = set()
            recipients.add(client.primary_eng)
            recipients.update(client.secondary_engs)
            recipients.add(client.account_contact)

            # don't email the person who added the
            # doc or anyone who's listed as an "author"
            recipients = recipients - set(doc['author'])

            # XGEN-1047: always add certain users
            recipients.update([
                'dan@10gen.com',
                'sabina',
                'alvin',
                'spf13',
            ])

            # unless they created the doc
            recipients.discard(doc['web_user'])

            xgenners = crowd_api.get_users_for_group('10gen')
            email_by_username = dict((u['username'], u['mail']) for u in xgenners)
            name_by_username = dict((u['username'], u['displayName']) for u in xgenners)
            recipients = [email_by_username.get(r, r) for r in recipients]

            if recipients:
                subject = 'New Clienthub Doc: %s for %s' % (doc['_type'], client.name)
                body = ['Type:         %(type)s',
                        'Creator:      %(creator)s',
                        'Participants: %(participants)s',
                        'Summary:      %(summary)s',
                        '',
                        '%(link)s',]

                body = '\n'.join(body)
                body = body % {
                    'type': doc['_type'],
                    'creator': name_by_username.get(doc['web_user'], doc['web_user']),
                    'participants': ', '.join(
                        name_by_username.get(u, u) for u in doc['author'] if u != doc['web_user']),
                    'summary': doc.get('summary', ''),
                    'link': web.ctx.homedomain + link('client.clientdocview', client._id, doc['_type'], doc['_id'])
                }
                web.utils.sendmail('info@10gen.com', recipients, subject, body)

        if save_and_stay:
            raise web.seeother(link('client.clientdocview', client_id, doc['_type'], doc_id))
        else:
            raise web.seeother(link('client.clientview', client_id))


class ClientUploadView(object):

    @authenticated
    def GET(self, client_id, file_id, filename):
        try:
            file_id = ObjectId(file_id)
            fp = gridfs.GridFS(environment['db'], 'clients.uploads').get(file_id)
        except gridfs.NoFile:
            raise app.notfound()

        if fp.content_type:
            web.header('Content-Type', fp.content_type)
            if fp.content_type.startswith('application'):
                web.header('Content-Disposition', 'attachment; filename=%s' % fp.filename)
        if fp.encoding:
            web.header('Content-Encoding', fp.encoding)

        chunk = fp.read(32768)
        while chunk != '':
            yield chunk
            chunk = fp.read(32768)

class DocumentSearch(object):

    @authenticated
    def GET(self):
        terms = web.input().get('search', '')
        results = None
        error = None
        clients = None

        if terms:
            try:
                output = environment['ftsdb'].command('fts', 'clients.docs', search=terms)
            except OperationFailure, of:
                error = str(of)
            else:
                results = [x['obj'] for x in output['results']]

                client_ids = set()
                for result in results:
                    client_ids.add(result['client_id'])

                clients = environment['db'].clients.find({'_id': {'$in': list(client_ids)}})
                clients = dict((c['_id'], Client()._from_db(c)) for c in clients)

                for result in results:
                    client = clients[result['client_id']]
                    result['client'] = client

        web.header('Content-Type', 'text/html')
        return env.get_template('docsearch.html').render(
            results=results,
            clients=clients,
            terms=terms,
            error=error,
        )


class ClientDocDelete(object):

    @authenticated
    def GET(self, client_id, doc_type, doc_id):
        doc_id = ObjectId(doc_id)
        doc = environment['db'].clients.docs.find_one({'_id': doc_id})
        if not doc:
            raise web.seeother(link('client.clientview', client_id))

        # delete attachments, if any
        if 'attachment' in doc:
            id = ObjectId(doc['attachment']['file_id'])
            environment['db'].clients.uploads.chunks.remove({'files_id': id})
            environment['db'].clients.uploads.files.remove({'_id': id})

        environment['db'].clients.docs.remove({'_id': doc_id})
        raise web.seeother(link('client.clientview', client_id))


