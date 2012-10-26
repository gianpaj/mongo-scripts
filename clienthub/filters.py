# -*- coding: utf-8 -*-
import re
import markdown2

from datetime import date, datetime, timedelta

import pytz
import web
import urllib

from config import env
from config import environment

def filter(func):
    name = func.__name__
    env.filters[name] = func
    return func

@filter
def datetimeformat(value, format='%H:%M / %d-%m-%Y', fromtimezone='UTC', totimezone='America/New_York'):
    if not value:
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=pytz.timezone(fromtimezone))
    value = value.astimezone(pytz.timezone(totimezone))
    return value.strftime(format)

@filter
def isfuture(value, extra_hours=0):
    if not isinstance(value, (datetime, date)):
        return False

    if isinstance(value, datetime):
        # compare to right now; assume UTC
        return datetime.utcnow() <= value + timedelta(hours=extra_hours)
    else:
        return date.today() < value

@filter
def staticurl(url, paramname='_ds', deploy_stamp=None):

    '''
    Adds ``deploy_stamp`` as the ``paramname`` query string parameter of the
    given url for caching. Assumes arguments are already valid url components.

    >>> staticurl('/static/foo', deploy_stamp='0')
    '/static/foo?_ds=0'
    '''
    if not deploy_stamp:
        deploy_stamp = environment["setup_time"]
    if '?' in url:
        return '%s&%s=%s' % (url, paramname, deploy_stamp)
    return '%s?%s=%s' % (url, paramname, deploy_stamp)

@filter
def abbrev(value, maxlen=150):
    if not isinstance(value, basestring):
        value = unicode(value)
    if len(value) > maxlen:
        after = value.find(' ', maxlen)
        if after == -1:
            after = maxlen
        before = value[:after].rfind(' ')
        if (after - maxlen) < (maxlen - before):
            split = after
        else:
            split = before
        return value[:split] + '...'
    return value

"""@filter
def htmlabbrev(value, maxlen=150):
    parser = HTMLAbbrev(maxlen)
    parser.feed(value)
    return parser.close()"""
@filter
def undo_smartquotes(value):
    value = value.replace('\xe2\x80\x99', "'")
    value = value.replace('\xe2\x80\x9c', '"')
    value = value.replace('\xe2\x80\x9d', '"')
    return value

@filter
def htmllength(value, maxlen=150):
    parser = HTMLAbbrev(maxlen)
    parser.feed(value)
    return parser.length

@filter
def get_field(value, dotted_name):
    """
    >>> value = {
    ...     'foo': 'foovalue',
    ...     'bar': [1, 2, 3],
    ...     'baz': [
    ...         {'name': 'b', 'value': 'd'},
    ...         {'name': 'B', 'value': 'D'},
    ...     ],
    ... }
    >>> get_field(value, 'foo')
    'foovalue'
    >>> get_field(value, 'bar.0')
    1
    >>> get_field(value, 'baz.1.name')
    'B'
    """
    try:
        obj = value
        for part in dotted_name.split('.'):
            if part.isdigit() and isinstance(obj, list):
                index = int(part)
                obj = obj[index]
            else:
                obj = obj[part]
        return obj
    except:
        # TODO: should we raise?
        return None

nozero_re = re.compile(r'(?:^|\s)0(\d)')

@filter
def nozero(value):
    """
    >>> nozero("March 03, 2011")
    'March 3, 2011'
    """
    return nozero_re.sub(r' \1', value)

@filter
def ordinal(value):
    """
    >>> [ordinal(x) for x in range(22)]
    ['0th', '1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th', '11th', '12th', '13th', '14th', '15th', '16th', '17th', '18th', '19th', '20th', '21st']
    >>> ordinal('foo bar 1')
    'foo bar 1st'
    """
    if isinstance(value, (int, long)):
        value = str(value)

    if not isinstance(value, basestring):
        return value

    if not value.isdigit():
        leader, digits = re.match(r'^(.*?)(\d*)$', value).groups()
        return leader + ordinal(digits)

    else:
        num = int(value)
        last = num % 10
        specials = {
            1: 'st', 2: 'nd', 3: 'rd'
        }
        if 10 <= num and num <= 20:
            return str(num) + 'th'
        if last in specials:
            return str(num) + specials[last]
        else:
            return str(num) + 'th'

ADWORDS_URL = 'http://www.google.com/aclk'
def from_adwords():
    return web.ctx.environ.get("HTTP_REFERER", '').lower().startswith(ADWORDS_URL)
env.globals.update(from_adwords=from_adwords)

@filter
def dictby(sequence, keyfield):
    out = {}
    for element in sequence:
        key = getattr(element, keyfield, element.get(keyfield, None))
        if key is None:
            continue
        out[key] = element
    return out

@filter
def noNone(value):
    if value is None:
        return ''
    return value

tag_re = re.compile(r'<[^>]+>')

@filter
def paragraphize(value):
    # if the value is already HTML formatted, return as-is;
    # otherwise, add paragraphs around chunks of text separated
    # by one (or more) blank lines. like low-fi markdown
    if type(value) not in (str, unicode):
        return value
    if tag_re.match(value):
        return value
    grafs = re.split('\n\n+', value)
    print '<p>%s</p>' % '</p><p>'.join(grafs)
    return '<p>%s</p>' % '</p><p>'.join(grafs)

@filter
def markdown(value):
    return markdown2.markdown(value)

@filter
def agenda_times(agenda):
    start = datetime.now(pytz.utc).replace(hour=0, minute=0, second=0) + timedelta(minutes=agenda['start'])
    start = start.strftime('%I:%M %p').lstrip('0').lower()
    end = datetime.now(pytz.utc).replace(hour=0, minute=0, second=0) + timedelta(minutes=agenda['end'])
    end = end.strftime('%I:%M %p').lstrip('0').lower()
    return '<nobr>%s -</nobr> <nobr>%s</nobr>' % (start, end)

@filter
def element_has(values, attr):
    for element in values:
        if attr in element and element[attr]:
            return True
    return False

@filter
def pluralize(value):
    if not isinstance(value, basestring):
        return value
    if value.endswith('s'):
        return value
    return value + 's'

joblocation_map = {
    'New York, NY': 'New York',
    'Redwood Shores, CA': 'Bay Area',
    'Dublin, Ireland, United Kingdom': 'Dublin, Ireland',
}

@filter
def joblocation(value):
    if 'variants' in value:
        locations = [v['location'] for v in value['variants']]
        locations = [joblocation_map.get(l, l) for l in locations]
        return ' / '.join(locations)
    elif 'location' in value:
        return joblocation_map.get(value['location'], value['location'])
    return value


jql_url = 'https://jira.mongodb.org/secure/IssueNavigator!executeAdvanced.jspa?runQuery=true&clear=true&jqlQuery='
def _jira_filter(query):
    def do_jira_filter(client):
        if client.jira_group:
            num_params = len(re.findall('%s', query))
            params = tuple([client.jira_group] * num_params)
            return jql_url + urllib.quote(query % params, safe='')
        elif client._id:
            return '/clienthub/edit/%s?message=To+use+JIRA+links,+you+must+assign+a+JIRA+group' % client._id
        else:
            # hopefully we won't get here
            return None
    return do_jira_filter

@filter
def jira_opencases_link(value):
    return _jira_filter('reporter in membersOf("%s") and status not in ("Closed", "Resolved")')(value)

@filter
def jira_allcases_link(value):
   return _jira_filter('reporter in membersOf("%s")')(value)

@filter
def jira_voted_watched_link(value):
    return _jira_filter('reporter in membersOf("%s") or watcher in membersOf("%s") or voter in membersOf("%s")')(value)


