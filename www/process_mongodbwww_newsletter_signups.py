#!/usr/bin/env python

import pymongo
import settings
from datetime import datetime
from sforce.enterprise import SforceEnterpriseClient
from sys import stdout
from traceback import print_exc
from webpy_mongodb_sessions.session import MongoStore

utcnow = datetime.utcnow

db = pymongo.Connection(settings.mongowwwdb_host).mongodb_www
sessionstore = MongoStore(db, 'sessions')

mongodb_download_campaign_id = '701A00000001Scg'
def create_lead(sfclient, email, state, country, campaignid=mongodb_download_campaign_id):
    lead = sfclient.generateObject('Lead')
    lead.Email = email
    lead.State = state
    lead.Country = country
    # XXX salesforce rejects if these are blank:
    lead.LastName = '[not specified]'
    lead.Company = '[not specified]'
    result = sfclient.create(lead)
    assert result['success'], 'Failed to create salesforce lead object'
    # associate lead with campaign
    leadId = result['id']
    cmember = sfclient.generateObject('CampaignMember')
    cmember.CampaignId = campaignid
    cmember.LeadId = leadId
    result = sfclient.create(cmember)
    assert result['success'], 'Failed to create salesforce campaign member object'

def main(verbose=False):
    sfclient = SforceEnterpriseClient('enterprise.wsdl.xml')
    sfclient.login(
        settings.salesforce['username'],
        settings.salesforce['password'],
        settings.salesforce['security_token'])
    nsuccess = nfail = ntotal = 0
    while True:
        # look for an unprocessed doc
        doc = db.newsletter_signups.find_one({'processed': False})
        if not doc:
            break
        ntotal += 1
        docid = doc['_id']
        sessionid = doc['sessionid']
        session = sessionstore[sessionid]
        email = session.get('email')
        if not email:
            db.newsletter_signups.update({'_id': docid}, {'$set': {'processed':
                'failed', 'exception': 'session missing email', 'timep':
                utcnow()}}, safe=True)
            continue
        ip = session['ip']
        ipinfo = db.ipinfo.find_one(ip)
        state = country = ''
        if ipinfo:
            try:
                state = ipinfo['Location']['StateData']['state_code']
                country = ipinfo['Location']['CountryData']['country_code']
            except KeyError:
                pass
        stdout.write('%4d. Processing %s... ' % (ntotal, email))
        try:
            create_lead(sfclient, email, state, country)
        except Exception, e:
            nfail += 1
            stdout.write('fail\n')
            if verbose:
                print_exc()
            db.newsletter_signups.update({'_id': docid}, {'$set': {'processed':
                'failed', 'exception': str(e), 'timep': utcnow()}}, safe=True)
        else:
            nsuccess += 1
            stdout.write('ok\n')
            db.newsletter_signups.update({'_id': docid}, {'$set': {'processed':
                True, 'timep': utcnow()}}, safe=True)

    stdout.write('Done. %d successes, %d failures, %d total.\n' %
        (nsuccess, nfail, ntotal))

if __name__ == '__main__':
    from sys import argv
    verbose = argv[1:2] == ['-v']
    main(verbose=verbose)
