#!/usr/bin/env python

import os, sys
here = os.path.dirname(os.path.abspath(__file__))
if here not in sys.path:
    sys.path.append(here)
import settings
from sforce.enterprise import SforceEnterpriseClient

mongodb_download_campaign_id = '701A00000001Scg'

def main():
    sfclient = SforceEnterpriseClient('file://' + here + '/enterprise.wsdl.xml')
    sfclient.login(
        settings.salesforce['username'],
        settings.salesforce['password'],
        settings.salesforce['security_token'])
    result = sfclient.queryAll(
        "SELECT LeadId FROM CampaignMember WHERE CampaignId='" +
        mongodb_download_campaign_id + "'")
    for i in result.records:
        lead = sfclient.generateObject('lead')
        lead.Id = i.LeadId
        lead.LeadSource = 'NewsletterSingup' # sic
        sfclient.update(lead)

if __name__ == '__main__':
    main()
