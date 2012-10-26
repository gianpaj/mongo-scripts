# -*- coding: utf-8 -*-

import collections
import datetime
import time
import traceback
import pytz
import logging

import pymongo
from bson.objectid import ObjectId

import web
import config
from config import app
from config import env
from config import environment
import filters

from corplibs.authenticate import authenticated
from corplibs.jira_suds import JiraAPI
from corplibs.salesforce import SalesforceAPI
from corplibs.xgencrowd import CrowdAPI
from corplibs.webutils import link
from models import Client

jira_api = JiraAPI()
crowd_api = CrowdAPI()
salesforce_api = SalesforceAPI()

_logger = logging.getLogger(__name__)

def last_by(things, key):
    if not things:
        return None

    newthings = list(things)
    newthings.sort(key=lambda thing: thing[key])
    return newthings[-1]

class Report(object):
    # subclasses should set name to a brief
    # internal name used for identifying report
    # runs in the database; this should not
    # change once set, as it will orphan old
    # report results
    name = None

    # subclasses should set display_name to
    # a human-readable name used in the web
    # interface
    display_name = None

    # subclasses should set description to a
    # brief description of the output of the
    # report, which will be used in the web
    # interface. the description may contain
    # HTML, and will be wrapped in <p>..</p>
    # if it seems appropriate
    _description = None

    @property
    def description(self):
        d = self._description.strip()
        if not d.startswith('<'):
            return '<p>%s</p>' % d
        return d

    def schedule(self, notify=[]):
        # add a row to the database to schedule
        # the report. reports are run by a cron
        # job in the background, at most one
        # report running per cron'd host
        if self.name is None:
            raise Exception('name must not be None when scheduling reports')

        environment['auxdb'].reports.save({
            'name': self.name,
            'scheduled': datetime.datetime.utcnow(),
            'status': 'new',
            'notify': notify,
            'webhost': web.ctx.homedomain,
        }, safe=True)

    def get_last(self):
        # return the db record of the last run, or
        # None if no run of this report has even
        # been finished
        curs = environment['auxdb'].reports.find({
            'name': self.name,
            'status': 'finished',
            'error': {'$exists': False}
        })
        curs.sort('scheduled', pymongo.DESCENDING)
        curs.limit(1)

        last = None
        for row in curs:
            last = row
        return last

    def get_next(self):
        # return the db record of the next scheduled
        # run (which may be an in-progress run) or
        # None if no run of this report has even
        # been scheduled
        curs = environment['auxdb'].reports.find({'name': self.name, 'status': {'$in': ['new', 'started']}})
        curs.sort('scheduled', pymongo.ASCENDING)
        curs.limit(1)

        last = None
        for row in curs:
            last = row
        return last

    @staticmethod
    def start_one():
        # get the oldest scheduled report
        # in the "new" state, and run it.
        # return the completed report's
        # record if successful, or None if
        # no reports were in the "new" state
        try:
            run_record = environment['auxdb'].reports.find_and_modify(
                query={'status': 'new'},
                sort={'scheduled': pymongo.ASCENDING},
                update={'$set': {'status': 'started'}},
                new=True)
        except OperationFailure:
            # couldn't find a report with status 'new'
            return None

        if run_record is None:
            return None

        try:
            report = REPORTS[run_record['name']]
        except KeyError:
            # no report class has this name; for now,
            # just ignore it
            return None

        try:
            s = time.time()
            report.run(run_record)
        except:
            e = time.time()
            run_record['run_time'] = (e - s)
            failure = traceback.format_exc()
            run_record['error'] = failure
            environment['auxdb'].reports.save(run_record)
            raise
        finally:
            e = time.time()
            run_record['run_time'] = (e - s)
            run_record['status'] = 'finished'
            run_record['finished'] = datetime.datetime.utcnow()
            environment['auxdb'].reports.save(run_record)

            # do notifications
            if run_record['notify']:
                to_addrs = run_record['notify']
                if 'error' in run_record:
                    subject = 'ClientHub Report failed'
                    body = 'Traceback:\n\n%s' % run_record['error']
                else:
                    subject = 'ClientHub Report finished'
                    body = link(app, 'report.clienthubviewreport', run_record['_id'])
                    body = run_record['webhost'] + body

                try:
                    web.utils.sendmail('www@10gen.com', to_addrs, subject, body)
                except:
                    pass

        return run_record

    def run(self, run_record):
        # subclasses should override this method
        # to execute the requested report, and save
        # results into the given run_record
        #
        # subclasses should add a dict to the
        # record named "out", with keys "fields"
        # and "rows". fields is a string column
        # headings, and rows is a list of dicts
        # keyed by the column headings. if the
        # row contains "_id", it will be assumed
        # to be a Client id, and will generate
        # a link to the given client for the row.
        # note that a header need not be present
        # for the _id autolinking to work.
        #
        # additionally, the row may contain two
        # keys, "_warnings" and "_errors" (both
        # lists), which, if present, will cause
        # the columns named to be highlighted
        # as a warning or an error, respectively
        pass


class CSConfig(Report):
    name = 'csconfig'
    display_name = 'Commercial Support Config Errors'
    _description = """
    <p>Find clients where one of the following is true:</p>
    <ul>
      <li>Client has an active support contract in
      Salesforce, but does not have a CS JIRA group</li>
      <li>Client has a CS JIRA group, but does not have
      a Salesforce account</li>
      <li>Client has a CS JIRA group and a Salesforce
      account, but no active support contract</li>
    </ul>"""

    def run(self, run_record):
        clients = [Client()._from_db(r) for r in db.clients.find()]

        cs_groups = jira_api.getGroupsInProjectRole('Customer', 'CS')
        cs_groups = [str(g['name']) for g in cs_groups]

        fields = ['Client Name', 'Recommendation', 'SF Account', 'Support Expires', 'JIRA Group', 'Is CS']
        rows = []

        for client in clients:
            row = {
                '_id': client._id,
                'Client Name': client.name,
                'Recommendation': '',
                'SF Account': client.sf_account_name,
                'Support Expires': '',
                'JIRA Group': client.jira_group,
                'Is CS': '',
                '_warnings': [],
                '_errors': [],
            }

            sf_contracts = client.get_sf_contracts()
            sf_contracts = filter(lambda c: c.get('is_active'), sf_contracts)

            has_sf = bool(client.sf_account_id)
            has_support = has_sf and bool(sf_contracts)
            has_jira = bool(client.jira_group)
            is_cs = has_jira and bool(client.jira_group in cs_groups)

            if is_cs:
                row['Is CS'] = 'Yes'
            elif has_jira:
                row['IS CS'] = 'No'

            if has_support:
                last_contract = last_by(sf_contracts, 'end')
                row['Support Expires'] = last_contract['end'].strftime('%Y-%m-%d')

            if has_support and not is_cs:
                row['Recommendation'] = 'Should be JIRA CS'
                row['_errors'].append('Is CS')
            elif is_cs and not has_sf:
                row['Recommendation'] = 'Configure SF Acct'
                row['_errors'].append('SF Account')
            elif is_cs and not has_support:
                row['Recommendation'] = 'Should not be JIRA CS'
                row['_errors'].append('Is CS')

            if not row['_warnings']:
                row.pop('_warnings')
            if not row['_errors']:
                row.pop('_errors')

            if row['Recommendation']:
                rows.append(row)

        run_record['out'] = {
            'fields': fields,
            'rows': rows
        }
        environment['auxdb'].reports.save(run_record)

class CountClients(Report):
    name = 'countclients'
    display_name = 'Assigned Client Count'
    _description = """
    Calculate the count of clients assigned to an engineer (as
    "primary engineer") or to a sales rep (only for accounts
    with salesforce configured).
    """

    def run(self, run_record):
        clients = [Client()._from_db(r) for r in db.clients.find()]

        xgenners = crowd_api.get_users_for_group('10gen')

        counts = collections.defaultdict(lambda: [None, 0, 0])
        for xgenner in xgenners:
            username = xgenner['username']
            realname = xgenner.get('displayName', username).strip()
            counts[username][0] = realname or username

        for client in clients:
            if client.primary_eng:
                counts[client.primary_eng][1] += 1
            if client.account_contact:
                counts[client.account_contact][2] += 1

        fields = ['User', '# Clients as Primary Eng', '# Clients as Account Contact']
        rows = []
        for username in sorted(counts.keys()):
            results = counts[username]
            rowdict = dict(zip(fields, results))
            rowdict['_link_' + fields[0]] = '%s?user=%s' % (link(app, 'client.clienthub'), username)
            rows.append(rowdict)

        run_record['out'] = {
            'fields': fields,
            'rows': rows,
        }
        environment['auxdb'].reports.save(run_record)

class ClientCheckins(Report):
    name = 'clientcheckins'
    display_name = 'Client Checkins'
    _description = """
    Summary information on the most recent checkin for each client.
    """

    def run(self, run_record):
        def last_by(things, key):
            if not things:
                return None

            newthings = list(things)
            newthings.sort(key=lambda thing: thing[key])
            return newthings[-1]

        def dt(dict, field):
            if not dict or field not in dict:
                return ''
            value = dict.get(field, None)
            if not value:
                return ''
            value = value.replace(tzinfo=pytz.UTC)
            value = value.astimezone(pytz.timezone('US/Eastern'))
            value = value.replace(tzinfo=None)
            return value.strftime('%Y-%m-%d')

        xgenners = dict((x['username'], x) for x in crowd_api.get_users_for_group('10gen'))
        status_map = jira_api.getStatusMap()

        cs_groups = jira_api.getGroupsInProjectRole('Customer', 'CS')
        cs_groups = set(g['name'] for g in cs_groups)

        fields = ['Client', 'Support Start', 'Last Checkin Ticket', 'Done', 'Assigned To', 'Last Checkin Doc']
        rows = []

        today = datetime.datetime.combine(
            datetime.date.today(),
            datetime.time(12, tzinfo=pytz.UTC)
        ).replace(tzinfo=None)
        ninety_days_ago = today - datetime.timedelta(days=90)

        issue_status = jira_api.getStatusMap()
        issue_status = dict((k, v['name']) for k, v in issue_status.items())
        issue_resolutions = jira_api.getResolutionMap()
        issue_resolutions = dict((k, v['name']) for k, v in issue_resolutions.items())

        for record in db.clients.find():
            client = Client()._from_db(record)

            # XGEN-984: entirely skip non-CS customers in this report
            if client.jira_group not in cs_groups:
                continue

            qualified = bool(client.sf_account_id and client.jira_group and client.primary_eng)
            if qualified:
                contracts = salesforce_api.get_active_support_contracts(client.sf_account_id)
                contracts = filter(lambda c: c.get('is_active'), contracts)
                last_contract = last_by(contracts, 'end')

                checkin_tickets = client.checkin_tickets
                last_checkin = last_by(checkin_tickets, 'created') or {}
                if last_checkin:
                    last_checkin = jira_api.get_issue(last_checkin.get('key')) or {}


                contract_start = dt(last_contract, 'start')
                checkin_created = dt(last_checkin, 'created')

                checkin_status = last_checkin.get('status')
                checkin_status = status_map.get(checkin_status, {})
                checkin_done = checkin_status.get('name') in ('Closed', 'Resolved')
                checkin_done = checkin_done and dt(last_checkin, 'updated') or ''

                checkin_user = last_checkin.get('assignee')
                checkin_user = xgenners.get(checkin_user, {}).get('displayName', '')

                checkin_key = last_checkin.get('key')
                if last_checkin:
                    checkin_ticket_info = ','.join((
                        issue_status.get(str(last_checkin.get('status')), 'Open'),
                        issue_resolutions.get(str(last_checkin.get('resolution')), '')
                    )).strip().strip(',')

                    ticket_info = '%s (%s)' % (checkin_key, checkin_ticket_info)
                else:
                    ticket_info = checkin_key


                checkin_docs = db.clients.docs.find({'client_id': client._id, "$or":{'_type': 'quarterly', '_type': 'clientcheckin'}})
                checkin_docs = list(checkin_docs)
                if checkin_docs:
                    checkin_doc = last_by(checkin_docs, 'created')['_id']
                else:
                    checkin_doc = ''

                row = [
                    client.name,
                    contract_start,
                    ticket_info,
                    checkin_done,
                    checkin_user,
                    checkin_doc,
                ]
            else:
                row = [client.name, '', '', '', '', '']

            row = dict(zip(fields, row))
            row['_id'] = client._id

            if row['Last Checkin Doc']:
                row['_link_Last Checkin Doc'] = link(app, 'doc.clientdocview', client._id, 'clientcheckin', row['Last Checkin Doc'])
                row['Last Checkin Doc'] = str(row['Last Checkin Doc'])[:8] + '...'

            if row['Last Checkin Ticket']:
                row['_link_Last Checkin Ticket'] = 'https://jira.mongodb.org/browse/%s' % checkin_key


            rows.append(row)

        run_record['out'] = {
            'fields': fields,
            'rows': rows,
        }
        environment['auxdb'].reports.save(run_record)


REPORTS = (CSConfig, CountClients, ClientCheckins)

# convert it to a dict by name
REPORTS = dict((r.name, r()) for r in REPORTS)

class ClientHubReports(object):

    @authenticated
    def GET(self):
        reports = REPORTS.values()
        reports.sort(key=lambda r: r.name)

        web.header('Content-Type', 'text/html')
        return env.get_template('reports.html').render(
            reports=reports,
        )

class ClientHubScheduleReport(object):

    @authenticated
    def GET(self, reportname):
        report = REPORTS[reportname]

        web.header('Content-Type', 'text/html')
        return env.get_template('report_schedule.html').render(
            report=report,
        )

    @authenticated
    def POST(self, reportname):
        report = REPORTS[reportname]

        notify_users = web.input().get('notify', '')
        notify_users = [email.strip() for email in notify_users.split(',')]
        notify_users = [email for email in notify_users if email]

        report.schedule(notify=notify_users)

        raise web.seeother(link(app, 'report.clienthubreports'))

class ClientHubViewReport(object):

    def GET(self, report_run_id):
        result = environment['auxdb'].reports.find_one({'_id': ObjectId(report_run_id)})
        if not result:
            raise web.seeother(link(app, 'report.clienthubreports'))

        report = REPORTS[result['name']]

        web.header('Content-Type', 'text/html')
        return env.get_template('report_view.html').render(
            report=report,
            result=result,
        )

