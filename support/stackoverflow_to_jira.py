import sys
from os.path import abspath, dirname, join

here = dirname(__file__)
sys.path.append(abspath(join(here, '..')))

from datetime import datetime, timedelta
import pytz
import pymongo
from BeautifulSoup import BeautifulSoup as Soup

import lib.stackoverflow
import lib.jira

def clean_html(html_str):
    return ''.join(Soup(html_str).findAll(text=True))


class StackOverflowImport(object):

    # questions before this datetime will never be
    # added to JIRA, even if they otherwise would be
    jira_cutoff = datetime(2011, 11, 20, 10, tzinfo=pytz.timezone('America/New_York'))

    def __init__(self):
        conn = pymongo.Connection('stats.10gen.cc', tz_aware=True)
        self.db = conn.support_so

        self.db.questions.ensure_index('updated')

    def run(self):
        # ensure that only one copy runs concurrently

        try:
            self.db.lock.save({'_id': 'stackoverflow', 'locked': False}, safe=True)
        except:
            # duplicate _id
            pass

        lock = self.db.lock.find_and_modify(
            {'_id': 'stackoverflow', 'locked': False},
            {'$set': {'locked': True}},
            new=True)

        if not lock:
            # another instance is running
            return

        try:
            self.main()
        finally:
            self.db.lock.update(
                {'_id': 'stackoverflow'},
                {'$set': {'locked': False}},
                safe=True)

    def main(self):
        # 1. scan for new questions, or updated questions,
        #    tagged "mongodb" in last 30 days
        # 2. for each question, create or update the db
        #    record of the question and any answers
        # 3. use db records to generate or update JIRA
        #    tickets

        fromdate = datetime.utcnow() - timedelta(days=30)
        fromdate = fromdate.replace(tzinfo=pytz.UTC)
        new_questions = lib.stackoverflow.get_questions_and_answers(
            tags=['mongodb'],
            fromdate=fromdate,
        )

        newly_answered_questions = set()
        question_count = 0
        for question in new_questions:
            question_count += 1

            question_id = question['question_id']

            if 'answers' not in question:
                question['answers'] = []

            db_question = self.db.questions.find_one({'_id': question_id})
            if not db_question:
                db_question = {
                    '_id': question_id,
                    'owner': question.get('owner', None),
                    'title': question['title'],
                    'tags': question['tags'],
                    'body': question['body'],
                    'answer_ids': [a['answer_id'] for a in question['answers']],
                    'answers': [
                        {'_id': a['answer_id'],
                         'owner': a.get('owner', None),
                         'body': a['body'],
                         'created': datetime.utcfromtimestamp(a['creation_date']),
                         'accepted': a['accepted'],
                         'in_jira': False,
                        }
                        for a in question['answers']],
                    'created': datetime.utcfromtimestamp(question['creation_date']),
                    'has_accepted_answer': max([a['accepted'] for a in question['answers']] + [False]),
                    'accepted_answer': max([a['answer_id'] for a in question['answers'] if a['accepted']] + [None]),
                    'url': 'http://stackoverflow.com/questions/%s' % question_id,
                    'jira': None,
                    'updated': datetime.utcnow(),
                }

            else:
                for answer in question['answers']:
                    if answer['accepted']:
                        if not db_question['has_accepted_answer']:
                            db_question['has_accepted_answer'] = True
                            newly_answered_questions.add(db_question['_id'])
                            print "accepted answer", answer['answer_id'], "(%s)" % db_question['_id']

                        if answer['answer_id'] != db_question['accepted_answer']:
                            db_question['accepted_answer'] = answer['answer_id']
                            db_question['updated'] = datetime.utcnow()

                    if answer['answer_id'] in db_question['answer_ids']:
                        continue

                    db_question['answer_ids'].append(answer['answer_id'])
                    db_question['answers'].append({
                        'id': answer['answer_id'],
                        'owner': answer.get('owner', None),
                        'body': answer['body'],
                        'created': datetime.utcfromtimestamp(answer['creation_date']),
                        'accepted': answer['accepted'],
                        'in_jira': False,
                    })
                    db_question['updated'] = datetime.utcnow()

            self.db.questions.save(db_question)


        jira = lib.jira.JiraConnection()
        for question in list(self.db.questions.find({'$or': [{'jira': None}, {"answers.in_jira": False}]})):
            if question['jira'] is None:
                if question['created'] >= self.jira_cutoff:
                    print "make jira for", question['url'],
                    res = jira.createIssue({
                        'project': 'FREE',
                        'type': '6', # question type
                        'summary': "SO: " + question['title'],
                        'description': '%s\nby: %s\n\n%s' % (question['url'],
                                                             question['owner']['display_name'],
                                                             clean_html(question['body'])),
                    })
                    question['jira'] = res['key']
                    self.db.questions.update({'_id': question['_id']}, {'$set': {'jira': res['key']}})
                    print "=>", res['key']
                else:
                    # question has no JIRA, but is too old;
                    # don't bother with its answers
                    continue

            if question['jira'] is None:
                # this shouldn't happen, but be safe
                continue

            for i, answer in enumerate(question['answers']):
                if not answer['in_jira']:
                    print "  add comment on", question['jira']
                    jira.addComment(question['jira'], {'body': 'by: %s\n\n%s' % (answer['owner']['display_name'],
                                                                                 clean_html(answer['body']))})
                    answer['in_jira'] = True
                    self.db.questions.update({'_id': question['_id']}, {'$set': {'answers.%d.in_jira' % i: True}})

        # jira constants
        #
        # it's crazy, but these are actually represented
        # as strings by the JIRA SOAP API
        OPEN = '1'
        IN_PROGRESS = '3'
        WAITING_FOR_CUSTOMER = '10006'
        CLOSED = '6'

        # map current state to action to "close & resolve";
        # None here means take no action, either because
        # it is not possible in the current workflow, or
        # because it makes no sense (eg when already closed)
        CLOSE_ACTIONS = {
            OPEN: '121',
            IN_PROGRESS: None,     # TODO: define this workflow step?
            WAITING_FOR_CUSTOMER: '111',
            CLOSED: None,
        }

        # close items for answered questions
        for question in self.db.questions.find({'_id': {'$in': list(newly_answered_questions)}}):
            if not question['jira']:
                # weird
                continue

            ticket = jira.getIssue(question['jira'])
            action = CLOSE_ACTIONS.get(ticket['status'])
            if action is not None:
                # close and resolve
                print "closing ticket", question['jira']
                jira.progressWorkflowAction(question['jira'], action)


if __name__ == '__main__':
    StackOverflowImport().run()
