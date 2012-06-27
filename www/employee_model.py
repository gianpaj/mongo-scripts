import web
import datetime
import pymongo
import gridfs
import md5
from bson.objectid import ObjectId

#LOCAL
connection = pymongo.Connection("localhost", 27017)
corpdb = connection.employee_info

	
def editable_keys():
	return ['intercall_code', 
			'secondary_phone_provider', 
			'employee_status', 
			'last_name', 
			'office', 
			'onsip_conf_bridge', 
			'twitter',  
			'seat', 
			'intercall_pin', 
			#'jira_uname', 
			'first_name', 
			'primary_phone', 
			'title', 
			'anniversary', 
			#'primary_email', 
			'secondary_phone', 
			'birthday', 
			'extension', 
			#'secondary_email', 
			'primary_phone_provider', 
			'primary_chat',
			'skills']


def display_keys():
	return ['email',
			'primary_phone',
			'primary_chat',
			'extension',
			'twitter',
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
			'jira_uname']
			
def generate_date(date_string):
	if len(date_string) != 0:
		split_date = date_string.split(" ")[0]
		split_date = split_date.split("-")
		
		day = int(split_date[0])
		month = int(split_date[1])
		year = int(split_date[2])
		date = datetime.datetime(year, month, day,0,0,0)
		return date

# returns a list of managers(cursors), taking into account manager override
def get_managers(employee):
	managers = []
	if "manager_ids" in employee.keys():
		print "manager_ids found in employee keys"
		for manager in corpdb.employees.find({"_id" : { "$in" : employee['manager_ids']}}):
			print "manager ids found"
			managers.append(manager)
	
	if "team_ids" in employee.keys() and employee['team_ids']:
		managing_team_ids = map(lambda team: team["_id"], corpdb.teams.find({"managing_team_ids": { "$in" : employee['team_ids']}})) # ids of teams managing teams employee belongs to
		print "managing_team_ids: ", managing_team_ids
		if managing_team_ids:
			for manager in corpdb.employees.find({"team_ids": managing_team_ids}):
				if manager not in managers:
					managers.append(manager)

	print "managers: ", managers
	return managers

# returns a list of teams(cursors)
def get_teams(employee):
	teams = {}
	if "team_ids" in employee.keys():
		for team_id in employee["team_ids"]:
			team = corpdb.teams.find_one({"_id" : ObjectId(team_id) })
			if team:
				teams[team_id] = {"name": team['name']}
	return teams

# primary email is whatever email is first in the email list
def primary_email(person):
    if 'email_addresses' in person.keys():
        if len(person['email_addresses']) > 0:
            return person['email_addresses'][0]
    else:
		return ""
	

def org_structure(team={}, parent="", org_list=[]):
	if len(team.keys()) == 0:
		CEO = corpdb.teams.find_one({"name" : "CEO"})
		org_list = []
		
		if CEO:
			org_list.append(["CEO", ""])
			for id in CEO['managing_team_ids']:
				team = corpdb.teams.find_one({"_id" : ObjectId(id) })
				org_list.append([team['name'], "CEO"])
				org_structure(team, team['name'], org_list)
			
	elif 'managing_team_ids' in team.keys():
		for id in team['managing_team_ids']:
			team = corpdb.teams.find_one({"_id" : ObjectId(id) })
			org_list.append([team['name'], parent])
			org_structure(team, team['name'], org_list)
		
	else:
		return []
		
	return org_list
	
def email_hash(employee):
    if len(employee['email_addresses']) > 0:
        primary_email = employee['email_addresses'][0]
        m = md5.new()
        m.update(primary_email.strip())

        try:
            return m.hexdigest()
        except:
            return ""
    else:
        return "" 
	
