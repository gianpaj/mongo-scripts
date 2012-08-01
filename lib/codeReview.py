"""
Library for code review tool
"""

import hashlib
import collections
import json
import logging
import os
import pytz # pip install pytz
import git # pip install GitPython
import datetime
import urllib
import web
import pymongo
from bson.objectid import ObjectId
import re
import time
import itertools
import sys

from corpbase import CorpBase, authenticated, wwwdb, eng_group, env
import gmail
import settings

pacific = pytz.timezone('US/Pacific') # github's timezone
eastern = pytz.timezone('US/Eastern') # our default timezone # TODO: detect user's timezone?!

def fix_id(obj):
    obj['id'] = str(obj['_id'])
    del obj['_id']
    return obj

def check_assignees(obj):
    for user in obj.get('assignees', []):
        if user not in eng_group:
            raise web.Conflict(
                "Can't assign to user %s because he/she is not in the group!" % user
            )

def get_repo_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, 'tmp_kernel_repo/mongo')

def get_repo():
    repo_dir = get_repo_dir()
    try:
        return git.Repo(repo_dir)
    except git.exc.NoSuchPathError:
        logging.info('cloning mongo repository from GitHub to %s' % repo_dir)
        basedir, leafdir = os.path.split(repo_dir)
        os.makedirs(basedir)
        os.system('cd %s; git clone git://github.com/mongodb/mongo.git; cd %s; git checkout v1.8; git checkout v2.0' % (
            basedir, leafdir
        ))
        return git.Repo(repo_dir)

def iter_commits(branch_name, stop_tag):
    """
    Iterate over commits in a branch, starting with the latest and going back to a tag.
    @param branch_name: Like 'v1.8'
    @param stop_tag:    A tag like 'r1.8.4', don't include this commit or its ancestors
    """
    repo = get_repo()

    try:
        branch = next(r for r in repo.branches if r.name == branch_name)
    except StopIteration:
        raise ValueError("No branch named %s" % branch_name)

    try:
        tag = next(t for t in repo.tags if t.name == stop_tag)
    except StopIteration:
        raise ValueError("No tag named %s" % stop_tag)

    if branch.commit == tag.commit:
        raise StopIteration

    yield branch.commit

    # TODO: use repo.commits_between()? or commits_since()? or log()? Is there some way to get all
    # the diffs in one shot instead of serially?
    for commit in branch.commit.iter_parents():
        if commit == tag.commit:
            raise StopIteration

        yield commit

def safe_remove(lst, item):
    """
    Like [].remove(), but no error if not present
    """
    try:
        lst.remove(item)
    except ValueError:
        pass

def diff(commit, parent):
    """
    @param commit:  A git.Commit object
    @return:        A dict like:
    {
        'added': ['foo.py'],
        'deleted': [],
        'modified': ['bar.py', 'baz.py'],
    }
    """
    rv = { 'added': [], 'deleted': [], 'modified': [] }
    if parent:
        diff_index = commit.diff(parent)
        for i in diff_index:
            path = i.a_blob.path
            if i.new_file:
                rv['added'].append(path)
            elif i.deleted_file:
                rv['deleted'].append(path)
            elif i.renamed:
                rv['renamed'].append(path)
            elif i.a_blob and i.b_blob and i.a_blob != i.b_blob:
                rv['modified'].append(path)

    return rv

def jsonify_commits(commits, branch_name):
    """
    @param commits:     Iterator of git.Commit objects
    @param branch_name: Like 'v1.8'
    @return:            List of JSON objects
    """
    lst = list(commits) # In case it's a generator

    return [
        {
            'author': {
                'name': commit.author.name,
                'email': commit.author.email,
                # email_md5 for generating the Gravatar URL
                'email_md5': md5(commit.author.email),
                },
            'date': commit_date_fmt(commit.authored_date),
            'timestamp': commit.authored_date,
            'message': commit.message,
            'hexsha': commit.hexsha,
            'diff': diff(commit, parent),
            'branch_name': branch_name,
        } for commit, parent in itertools.izip_longest(
            lst, lst[1:]
        )
    ]

def commits(branch_name, stop_tag, db, user):
    """
    List of Mongo kernel commits, starting at the tip of the branch and stopping just before stop_tag.
    @param branch_name:     Name of a release branch, e.g. "v2.0"
    @param stop_tag:        Tag before which to stop, e.g. "r2.0.1"
    @param db:              A Mongo database
    @param user:            Currently logged-in username, e.g. "jesse"
    """
    rv = jsonify_commits(iter_commits(branch_name, stop_tag), branch_name)

    if rv:
        # Merge in all the commit info -- who's accepted / rejected, to whom it's been assigned, etc.
        hexsha2db_commit = dict(
            (commit['hexsha'], commit)
            for commit in db.commit.find({
                'hexsha': { '$in': [commit['hexsha'] for commit in rv] },
            })
        )

        for git_commit in rv:
            # If user is 'jesse', transform from this:
            # {
            #     hexsha: 'abcdefg',
            #     accepted_by: ['jesse','eliot'],
            #     rejected_by: ['steve'],
            #     assigned_to: ['jesse','steve']
            # }
            # ... to this:
            # {
            #     hexsha: 'abcdefg',
            #     accepted_by: ['eliot'],
            #     rejected_by: ['steve'],
            #     assigned_to: ['jesse','steve'], # unchanged
            #     user_accepted: True,
            #     user_rejected: False,
            # }
            #
            # This ensures that if Eliot opens the code-review page and his browser loads the commit info,
            # then Jesse loads the info, then Eliot changes the info, then Jesse does, Jesse's changes don't
            # overwrite Eliot's.
            mongo_commit = hexsha2db_commit.get(git_commit['hexsha'], {})
            mongo_commit['user_accepted'] = (user in mongo_commit.get('accepted_by', []))
            safe_remove(mongo_commit.get('accepted_by', []), user)
            mongo_commit['user_rejected'] = (user in mongo_commit.get('rejected_by', []))
            safe_remove(mongo_commit.get('rejected_by', []), user)
            git_commit.update(mongo_commit)
            # ObjectId's aren't JSON serializable
            if '_id' in git_commit: del git_commit['_id']

        return rv
    else:
        raise ValueError("No branch named %s" % branch_name)

def md5(s):
    m = hashlib.md5()
    m.update(s)
    return m.hexdigest()

def commit_date_fmt(timestamp):
    """
    @param timestamp:   A unix timestamp, seconds since epoch, in Pacific time
    @return:            Formatted date in Eastern time
    """
    return datetime.datetime.fromtimestamp(
        timestamp, pacific
    ).astimezone(eastern).strftime('%Y-%m-%d %I:%M%p')

def commit_match(jsonified_commit, pattern):
    """
    @param commit:      A jsonified commit
    @param pattern:     A compiled regex
    @return:            True if any of the file paths modified by commit match pattern
    """
    for change_type, files in jsonified_commit['diff'].items():
        if any(file for file in files if pattern.search(file)):
            return True

    return False

class BadRegex(web.badrequest):
    def __init__(self, message):
        self.message = message
        web.badrequest.__init__(self)

class CodeReviewPatternTest(CorpBase):
    @authenticated
    def GET(self, pageParams, branch_name, stop_tag, pattern):
        """
        Let the user test an assignment-rule regex to see which past commits it would have matched
        """
        # pattern was encoded by Javascript with encodeURIComponent()
        web.header('Content-type','text/json')
        start = time.time()

        try:
            decoded_pattern = re.compile(urllib.unquote_plus(pattern))
        except re.error as e:
            raise BadRegex(str(e))

        rv = json.dumps([
            commit for commit in jsonify_commits(
                iter_commits(branch_name, stop_tag),
                branch_name,
            ) if commit_match(commit, decoded_pattern)
        ])
        logging.info('CodeReviewPatternTest.GET()', time.time() - start)
        return rv

class CodeReviewAssignmentRules(CorpBase):
    @authenticated
    def GET(self, pageParams):
        web.header('Content-type','text/json')
        return json.dumps([
            fix_id(rule)
            for rule in wwwdb.rule.find()
        ])

    @authenticated
    def POST(self, pageParams):
        """
        Create a new rule
        """
        rv = json.loads(web.data())
        check_assignees(rv)
        wwwdb.rule.save(rv)
        return json.dumps(fix_id(rv))

class CodeReviewAssignmentRule(CorpBase):
    @authenticated
    def GET(self, pageParams, _id):
        web.header('Content-type','text/json')
        return json.dumps(fix_id(wwwdb.rule.find({ '_id': ObjectId(_id) })))

    @authenticated
    def PUT(self, pageParams, _id):
        rv = json.loads(web.data())
        check_assignees(rv)
        rv['_id'] = ObjectId(_id)
        wwwdb.rule.save(rv)
        return json.dumps(fix_id(rv))

    @authenticated
    def DELETE(self, pageParams, _id):
        wwwdb.rule.remove({ '_id': ObjectId(_id) })
        return ""

def save_commit(hexsha, json, db, group, user):
    """
    @param hexsha:      A git commit hash
    @param json:        Like this:
    {
        hexsha: 'abcdefg',
        accepted_by: ['eliot'],
        rejected_by: ['steve'],
        assigned_to: ['steve'],
        user_accepted: True,
        user_rejected: False,
    }
    @param db:          A Mongo database
    @param group:       List of usernames
    @param user:        Currently logged-in username, e.g. "jesse"
    """
    assert user in group
    if 'assigned_to' in json:
        for assigned_user in json['assigned_to']:
            assert assigned_user in group, (
                "Commit can't be assigned to user %s because he/she is not in the group!" % assigned_user
            )
    db.commit.ensure_index('hexsha', unique=True)

    # This user is allowed to add to assignments, but not to delete assignments. She
    # can change her own accepted / rejected status.

    update = collections.defaultdict(dict, {
        '$addToSet': {
            'assigned_to': { '$each': json.get('assigned_to', []) },
        }
    })

    if json.get('user_accepted'):
        update['$addToSet']['accepted_by'] = user
        update['$pull']['rejected_by'] = user
    elif json.get('user_rejected'):
        update['$addToSet']['rejected_by'] = user
        update['$pull']['accepted_by'] = user
    else:
        update['$pull']['rejected_by'] = user
        update['$pull']['accepted_by'] = user

    db.commit.update({ 'hexsha': hexsha }, update, upsert=True, multi=False)

class CodeReviewCommits(CorpBase):
    @authenticated
    def GET(self, pageParams, branch_name, stop_tag):
        web.header('Content-type','text/json')
        start = time.time()
        rv = json.dumps(
            commits(
                branch_name=branch_name, stop_tag=stop_tag, db=wwwdb,
                user=pageParams['user'],
            )
        )
        logging.info('CodeReviewCommits.GET()', time.time() - start)
        return rv


class CodeReviewCommit(CorpBase):
    @authenticated
    def POST(self, pageParams, hexsha):
        try:
            save_commit(
                hexsha=hexsha,
                json=json.loads(web.data()),
                db=wwwdb,
                group=eng_group,
                user=pageParams['user'],
            )
            return json.dumps({})
        except Exception as e:
            raise web.Conflict(str(e))

class CodeReviewPostReceiveHook:
    def POST(self):
        """
        Receive a POST from GitHub telling us about a new set of commits. Respond in two ways:
        *) Check all the assignment rules and assign code reviews to people
        *) Update the local copy of the repository
        """
        logging.info('CodeReviewPostReceiveHook.POST():\n%s' % web.input().get('payload'))
        rules = []
        for rule in wwwdb.rule.find():
            try:
                rules.append({
                    'pattern': re.compile(rule['pattern']),
                    'assignees': rule['assignees']
                })
            except re.error:
                logging.error('Error with pattern: %s' % rule['pattern'])

        assignments = collections.defaultdict(set)

        payload = json.loads(web.input().get('payload'))

        if payload['repository']['name'] != 'mongo':
            logging.error('Post-commit hook for wrong repo: Should be "mongo", is %s' % payload['repository']['name'])
            return

        logging.info('CodeReviewPostReceiveHook.POST() got commits: %s' % [c.get('id') for c in payload.get('commits', [])])

        for commit in payload.get('commits', []):
            for file_list in [
                commit.get('added', []),
                commit.get('removed', []),
                commit.get('modified', []),
            ]:
                for file in file_list:
                    for rule in rules:
                        if rule['pattern'].match(file):
                            logging.info('assigning %s to %s, matches pattern "%s"' % (
                                commit['id'], rule['assignees'], rule['pattern'].pattern
                            ))
                            assignments[commit['id']].update(set(rule['assignees']))

        for hexsha, assignees in assignments.items():
            wwwdb.commit.update({
                'hexsha': hexsha,
            }, {
                '$addToSet': {
                    'assigned_to': { '$each': list(assignees) },
                }
            }, upsert=True, multi=False)

        # We know there are new commits in GitHub, so pull them to the local repo
        logging.info('Pulling repository from remote: %s' % get_repo_dir())
        os.system("cd '%s'; git pull --all" % get_repo_dir())
        logging.info('Pulled')

def nightly_email(dryrun, force):
    """
    Run this once a night in a cron job. It checks to ensure it hasn't already
    run tonight, using a unique document in www.codereview_emails.
    @param dryrun:      If True, don't actually send emails, print them to stdout
    @param force:       If True then run, even if this script has run before
    """
    # Like '2011-11-25'
    tonight = datetime.datetime.utcnow().strftime('%Y-%m-%d')

    # Ensure exactly one script sends the emails -- our crontab is stored in
    # https://github.com/10gen/ops/blob/master/cron/www-c/crontab
    # which is installed on multiple machines, but they all share a wwwdb
    try:
        wwwdb.codereview_emails.insert({
            '_id': tonight,
        }, safe=True)
    except pymongo.errors.DuplicateKeyError:
        if not force:
            logging.error(
                (
                    'Another script has already begun to email code reviews for'
                    ' %s, try --force?'
                ) % tonight
            )
            sys.exit(1)

    user2commits = collections.defaultdict(list)

    # Any commit that matches an assignment rule is assigned to a user in
    # CodeReviewPostReceiveHook.POST(), regardless of whether the commit is
    # in a release branch. So we need to iterate over commits that *are* in
    # release branches, check if they're assigned for review, and email users
    # to tell them to review the commits.
    for branch_config in [
        { 'branch_name': 'v1.8', 'stop_tag': 'r1.8.4' },
        { 'branch_name': 'v2.0', 'stop_tag': 'r2.0.1' },
    ]:
        for commit in commits(
            branch_name=branch_config['branch_name'],
            stop_tag=branch_config['stop_tag'],
            db=wwwdb,
            user=None,
        ):
            assignees = set(commit.get('assigned_to', []))
            reviewed_by = set(commit.get('rejected_by', [])).union(set(commit.get('accepted_by', [])))
            must_review = assignees.difference(reviewed_by)
            for user in must_review:
                user2commits[user].append(commit)

    n_reviews_total = len(set([commit['hexsha'] for commits_to_review in user2commits.values() for commit in commits_to_review]))

    for user, commits_to_review in user2commits.items():
        n_reviews = len(commits_to_review)
        logging.info('Emailing %s: %s reviews for her or him, %s reviews total' % (
            user, n_reviews, n_reviews_total
        ))

        # 'env' is a jinja2 environment imported from corpbase.py
        emailbody = env.get_template("codereview_email.txt").render(locals())
        if dryrun:
            print '-' * 75
            print user
            print emailbody
            print
        else:
            gm = gmail.gmail( settings.smtp["smtp_username"] , settings.smtp["smtp_password"] )
            gm.send_simple(user + "@10gen.com", "Your assigned code reviews", emailbody, replyto="noreply@10gen.com")
            logging.info('Emailed ' + user)
