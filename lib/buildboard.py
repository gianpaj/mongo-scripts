import requests
import json
import time
from functools import wraps

from corpbase import env, CorpBase, authenticated

memos = {}
def memoize_for(cache_for):
    def decorator(func):
        @wraps(func)
        def inner(*args):
            if func not in memos:
                memos[func] = {}
            if args not in memos[func]:
                memos[func][args] = (0, None)
            if (time.time() - memos[func][args][0]) > cache_for:
                out = func(*args)
                memos[func][args] = (time.time(), out)
            return memos[func][args][1]
        return inner
    return decorator

@memoize_for(300)
def get_builders():
    response = requests.get('http://buildbot.mongodb.org:8081/json/builders/')
    content = json.loads(response.content)
    return content.keys()

@memoize_for(60)
def get_last_builds(builder, num):
    qstring = '&'.join('select=%d' % n for n in xrange(-num, 0))
    response = requests.get('http://buildbot.mongodb.org:8081/json/builders/%s/builds/?filter=1&%s' % (builder, qstring))
    body = json.loads(response.content)
    out = []
    for n in reversed(range(-num, 0)):
        build = body[str(n)]
        build['name'] = builder
        build['links'] = {}
        build['links']['builder'] = 'http://buildbot.mongodb.org:8081/builders/%s' % (builder, )
        build['links']['build'] = 'http://buildbot.mongodb.org:8081/builders/%s/builds/%d' % (builder, n)
        build['links']['json'] = 'http://buildbot.mongodb.org:8081/json/builders/%s/builds/%d?as_text=1' % (builder, n)
        out.append(build)
    return out

def get_last_build(builder):
    return get_last_builds(builder, 1)[0]

def buildstatus(build):
    if 'text' in build:
        return ' '.join(build['text'])
    elif 'steps' in build:
        warning = False
        for step in build['steps']:
            if step.get('statistics', {}).get('warnings'):
                warning = True
                break
            if 'warnings' in step.get('text', []):
                warning = True
                break

        if warning:
            return 'running warning'
        return 'running inprog'

    return ''

def lastupdated(builder):
    return max(max(step.get('times', [0])) for step in builder.get('steps', []))

def history(builder):
    last_five = get_last_builds(builder['name'], 5)
    states = [buildstatus(build) for build in last_five]
    if all('failed' in state for state in states):
        return 'failing'
    elif all('successful' in state for state in states):
        return 'passing'
    return 'partfailing'

class BuildBoard(CorpBase):

    @authenticated
    def GET(self, pageParams):
        builds = [get_last_build(builder) for builder in get_builders()]
        return env.get_template('buildboard.html').render(
            builds=builds,
            buildstatus=buildstatus,
            lastupdated=lastupdated,
            history=history,
        )

