from datetime import datetime
from datetime import timedelta
import pymongo
import hashlib
from bson.objectid import ObjectId
from corpbase import corpdb
import math


def editable_keys():
    return ['intercall_code',
            'secondary_phone_provider',
            'employee_status',
            'last_name',
            'office',
            'onsip_conf_bridge',
            'twitter',
            'github',
            'seat',
            'intercall_pin',
            #'jira_uname',
            'first_name',
            'primary_phone',
            'title',
            'start_date',
            #'primary_email',
            'secondary_phone',
            'birthday',
            'extension',
            #'secondary_email',
            'primary_phone_provider',
            'primary_chat',
            'skills',
            'skype_id',
            'stackoverflow_id',
            'email_addresses',
            'manager_ids']


def display_keys():
    return ['email',
            'primary_phone',
            'primary_chat',
            'extension',
            'twitter',
            'github',
            'seat',
            'jira_uname']


def no_show():
    return ['_id',
            'id',
            'first_name',
            'last_name',
            'managing_ids',
            'team_ids',
            'skills',
            'title',
            'role',
            'jira_uname',
            'bio',
            'manager_ids']


def generate_date(date_string):
    if len(date_string) != 0:
        split_date = ""
        split_date = date_string.split(" ")[0]
        split_date = split_date.split("-")
        day = int(split_date[0])
        month = int(split_date[1])
        if (split_date.__len__() > 2):
            year = int(split_date[2])
        else:
            year = 2012
        date = datetime(year, month, day, 0, 0, 0)
        return date


def get_managers(employee):
    """returns a list of managers(cursors), taking into account manager override"""
    managers = []
    # "ad-hoc" managers
    if "manager_ids" in employee.keys():
        for manager in corpdb.employees.find({"_id": {"$in": employee['manager_ids']}, "employee_status": {"$ne": "Former"}}):
            managers.append(manager)

    # team managers
    if "team_ids" in employee.keys() and employee['team_ids']:
        # ids of teams managing teams employee belongs to
        managing_team_ids = map(lambda team: team["_id"],
                                corpdb.teams.find({"managing_team_ids": {"$in": employee['team_ids']}}))
        if managing_team_ids:
            for manager in corpdb.employees.find({"team_ids": {"$in": managing_team_ids}, "employee_status": {"$ne": "Former"}}):
                if manager not in managers:
                    managers.append(manager)
    return managers


def get_team_managers(employee):
    managers = []
    # team managers
    if "team_ids" in employee.keys() and employee['team_ids']:
         # ids of teams managing teams employee belongs to
        managing_team_ids = map(lambda team: team["_id"],
                                corpdb.teams.find({"managing_team_ids": {"$in": employee['team_ids']}}))
        if managing_team_ids:
            for manager in corpdb.employees.find({"team_ids": managing_team_ids, "employee_status": {"$ne": "Former"}}):
                if manager not in managers:
                    managers.append(manager)
    return managers

def get_ad_hoc_managers(employee):
    managers = []
    if "manager_ids" in employee.keys():
        for manager in corpdb.employees.find({"_id": {"$in": employee['manager_ids']},
                                              "employee_status": {"$ne": "Former"}}):
            managers.append(manager)
    return managers


def get_manager_hierarchies(employee):
    manager_hierarchies = []
    managers = get_team_managers(employee)

    if managers:
        for manager in managers:
            manager_hierarchy = []
            manager_list = []
            team_managers = []
            curr_employee = employee

            while employee['last_name'] != "Merriman":
                manager_list.append(manager['_id'])
                curr_employee = manager
                team_managers = get_team_managers(curr_employee)
                if (team_managers.__len__() > 0):
                    manager = team_managers[0]
                else:
                    break

            for manager_id in reversed(manager_list):
                manager = corpdb.employees.find_one(manager_id)
                manager_hierarchy.append(manager)

            manager_hierarchies.append(manager_hierarchy)

    return manager_hierarchies


def get_teams(employee):
    # returns a list of teams(cursors)
    teams = {}
    if "team_ids" in employee.keys():
        for team_id in employee["team_ids"]:
            team = corpdb.teams.find_one({"_id": ObjectId(team_id)})
            if team:
                teams[team_id] = {"name": team['name']}
    return teams


def primary_email(person):
    """primary email is whatever email is first in the email list"""
    if 'email_addresses' in person.keys():
        if len(person['email_addresses']) > 0:
            return person['email_addresses'][0]
    else:
        return ""


def org_structure(team={}, parent="", org_list=[]):
    if len(team.keys()) == 0:
        CEO = corpdb.teams.find_one({"name": "CEO"})
        org_list = []

        if CEO:
            org_list.append(["CEO", ""])
            for id in CEO['managing_team_ids']:
                team = corpdb.teams.find_one({"_id": ObjectId(id)})
                org_list.append([team['name'], "CEO"])
                org_structure(team, team['name'], org_list)
    elif 'managing_team_ids' in team.keys():
        for id in team['managing_team_ids']:
            team = corpdb.teams.find_one({"_id": ObjectId(id)})
            org_list.append([team['name'], parent])
            org_structure(team, team['name'], org_list)

    else:
        return []

    return org_list


def org_structure_list(team=None):
    if team is None:
        team = corpdb.teams.find_one({"name": "CEO"})
    org_list = ""
    if 'managing_team_ids' in team.keys():
        org_list = "<li>" + team['name'] + "<br/>"
        for employee in corpdb.employees.find({"team_ids": team['_id'], "employee_status": {"$ne": "Former"}}):
            org_list = org_list + "<p><a href='employees/" + employee['jira_uname'] + "'>" + employee['first_name'] + " " + employee['last_name'] + "</a></p>"
        org_list = org_list + "<ul>"
        managing_list = ""
        for id in team['managing_team_ids']:
            team = corpdb.teams.find_one({"_id": ObjectId(id)})
            managing_list = managing_list + org_structure_list(team)
        org_list = org_list + managing_list + "</ul></li>"

    else:
        org_list = "<li>" + team['name'] + "<br/>"
        for employee in corpdb.employees.find({"team_ids": team['_id'], "employee_status": {"$ne": "Former"}}):
            org_list = org_list + "<p><a href='employees/" + employee['jira_uname'] + "'>" + employee['first_name'] + " " + employee['last_name'] + "</a></p>"
        org_list = org_list + "</li>"

    return org_list


def email_hash(employee):
    if len(employee['email_addresses']) > 0:
        primary_email = employee['email_addresses'][0]
        m = hashlib.md5()
        m.update(primary_email.strip())

        try:
            return m.hexdigest()
        except:
            return ""
    else:
        return ""


def to_vcard(employee):
    vcard = ""
    if employee['last_name'] and employee['first_name'] and len(employee['email_addresses']) > 0:
        vcard = "BEGIN:VCARD\n"
        vcard += "VERSION:3.0\n"
        vcard += "N:" + employee['last_name'].strip() + ";" + employee['first_name'].strip() + ";;;" + "\n"
        vcard += "FN:" + employee['first_name'].strip() + " " + employee['last_name'].strip() + "\n"
        vcard += "ORG:10gen\n"
        vcard += "TITLE:" + employee['title'].strip() + "\n"
        vcard += "TEL;TYPE=WORK:" + employee['primary_phone'].strip() + "\n"
        vcard += "EMAIL;TYPE=INTERNET:" + employee['email_addresses'][0].strip() + "\n"
        vcard += "REV:" + datetime.utcnow().strftime("%Y%m%d%H%M%S") + "\n"
        vcard += "END:VCARD"

    return vcard


# Returns today's date.
def get_date():
	return datetime.now()

def add_days_to_date(date, days):
	days = timedelta(days = days)
	return (date + days)

def review_overdue(created_date):
	return complete_by_date < datetime.now()

# Returns list of performance review questions:
def get_questions(review_type):
	if (review_type == "Employee"):
		return ['How do you provide value?  In what areas are you amazing?  Provide an example of something you did that was particularly positive over the past period or year.',
				'Identify something you did that was neat, unorthodox, clever, innovative, crazy-but-turns-out-to-be-useful, etc.',
				'Over the course of this year or period, what have been your strength areas?',
				'Over the course of the past year or period, what could you have improved?',
				'How are you active with the 10gen community?',
				'Are you happy? Are you having fun? What are your aspirations for growth?',
				'Plan; identify a few high level, strategic goals to accomplish over the course of the following period or year.'
				]
	elif (review_type == "Manager"):
		return ['Where does your employee provide value?  In what areas is she/he amazing?  Provide an example of something he/she did that was particularly positive over the past period or year.',
				'Identify something he/she did that was neat, unorthodox, clever, innovative, crazy-but-turns-out-to-be-useful, etc.',
				'Over the course of this year, what would you say are his/her strengths?',
				'Over the course of the past year, what would you say are his/her weaknesses?',
				'How is he/she active with the 10gen community?',
				'Question to pose to the employee:  Are you happy? Are you having fun? What are your aspirations for growth?',
				'Plan; identify a few high level, strategic goals to accomplish over the course of the following year.'
				]
	else:
		return []

# Returns a list of performance review question placeholders.
def get_placeholders(review_type):
	if(review_type == "Employee"):
		return ['',
				'think differently!',
				'',
				'weaknesses are hard to fix. either have a hard plan to fix the item or propose a work-around',
				'i.e. give a talk, volunteer at a recruiting event, attend a tech talk',
				'i.e. what do you enjoy about 10gen and what would make your experience better?',
				''
				]
	elif(review_type == "Manager"):
		return ['i.e. nudge that you have to be really good here - at something.  doing 10 jiras in a mad overnight session might be a good example; so it is not impossible!',
				'nudge to think differently. e.g. "give away mms,"',
				'',
				'weaknesses are hard to fix. either have a hard plan to fix the item, or propose workarounds, or just decide that for the job at hand they are not important.',
				'this could probably be measured objectively using variation indirect metrics out there',
				'this is career planning section for the 20 percent for whom that is the right thing to talk about.  sometimes it is not about career planning maybe it is a no-op or maybe it is "i want to do something different or learn xyz" instead.',
				''
				]
	else:
		return []

