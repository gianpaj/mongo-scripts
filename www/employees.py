import os
import sys
import web
import pymongo
import gridfs
from bson.objectid import ObjectId
import hashlib
import hmac
import jinja2
import employee_model
import random
import csv
from util import _url_split, url_cmp
from corpbase import env, CorpBase, authenticated, the_crowd, eng_group, wwwdb, mongowwwdb, usagedb, pstatsdb, corpdb, ftsdb
from functools import wraps
from datetime import datetime
try:
    import cStringIO as StringIO
except:
    import StringIO

############### Roles and Control Wrappers #################
############################################################
def require_manager(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            crowd_uname = args[0]['user']
            current_user = corpdb.employees.find_one({"jira_uname" : crowd_uname })
            roles = current_user['roles']
        except:
            current_user = None
            roles = []
        if "manager" in roles :
            return f(self, *args, **kwargs)
        raise web.seeother('/employees')

    return wrapper

def require_admin(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            crowd_uname = args[0]['user']
            current_user = corpdb.employees.find_one({"jira_uname" : crowd_uname })
            roles = current_user['roles']
        except:
            current_user = None
            roles = []
        if "admin" in roles:
            return f(self, *args, **kwargs)
        raise web.seeother('/employees')

    return wrapper

def require_admin_or_manager(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            crowd_uname = args[0]['user']
            current_user = corpdb.employees.find_one({"jira_uname" : crowd_uname })
            roles = current_user['roles']
        except:
            current_user = None
            role = []
        if "admin" in roles or "manager" in roles:
            return f(self, *args, **kwargs)
        raise web.seeother('/employees')

    return wrapper

def require_current_user(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
       try:
            crowd_uname = args[0]['user']
            current_user = corpdb.employees.find_one({"jira_uname" : crowd_uname })
            requested_employee = corpdb.employees.find_one({"jira_uname": args[1] })
            if not requested_employee:
                 requested_employee = corpdb.employees.find_one({"_id": ObjectId(args[1]) })
       except:
            current_user = None
            requested_employee = None
       if requested_employee and current_user:
           if requested_employee['jira_uname'] == crowd_uname:
               return f(self, *args, **kwargs)
       raise web.seeother('/employees')

    return wrapper

def require_manager_admin_or_self(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
       try:
            crowd_uname = args[0]['user']
            current_user = corpdb.employees.find_one({"jira_uname" : crowd_uname })
            requested_employee = corpdb.employees.find_one({"jira_uname": args[1] })
            if not requested_employee:
                 requested_employee = corpdb.employees.find_one({"_id": ObjectId(args[1]) })
       except:
            current_user = None
            requested_employee = None

       if requested_employee and current_user:
           print "requested employee: ", requested_employee['jira_uname']
           requested_employees_managers = employee_model.get_managers(requested_employee)
           if current_user in requested_employees_managers or current_user["jira_uname"] == requested_employee["jira_uname"] or "admin" in current_user['roles']:
               return f(self, *args, **kwargs)
       raise web.seeother('/employees')
    return wrapper


############################################################
# helper functions
############################################################
def md5(s):
    m = hashlib.md5()
    m.update(s)
    return m.hexdigest()

def current_user_roles(pp):
    crowd_name = pp['user']
    current_user = corpdb.employees.find_one({"jira_uname" : crowd_name })
    try:
        roles = current_user['roles']
    except:
        roles = ["employee"]
    return roles


############################################################
# Employees
############################################################
class EmployeesIndex(CorpBase):
    @authenticated
    def GET(self, pp):
        print "GET EmployeesIndex"
        
        # this isn't the most efficient way of getting a random document, but the collection is too small for it really to matter
        range_max = corpdb.employees.find({"employee_status" : {"$ne": "Former"}}).count()
        if range_max > 1:
            random_int = random.randint(1, range_max)
            pp['random_employee'] = corpdb.employees.find({"employee_status" : {"$ne" : "Former"}}).skip(random_int-1).next()
            pp['random_employee_primary_email'] = employee_model.primary_email(pp['random_employee'])
            # Set up hash for getting gravatar
            if pp['random_employee_primary_email']:
                pp['random_employee_hash'] = md5(pp['random_employee_primary_email'].strip())
            else:
                pp['random_employee_hash'] = ""

        pp['current_user_roles'] = current_user_roles(pp)
        if "admin" in pp['current_user_roles']:
            pp['employees'] = corpdb.employees.find().sort("last_name", pymongo.ASCENDING)
        else:
            pp['employees'] = corpdb.employees.find({"employee_status" : {"$ne": "Former"}}).sort("last_name", pymongo.ASCENDING)

        return env.get_template('employees/employees/index.html').render(pp=pp)

    #SEARCH FORM SUBMITS TO HERE
    @authenticated
    def POST(self, pp):
        print "POST index"
        form = web.input()
        if 'search' in form.keys():
            employee = corpdb.employees.find_one({"jira_uname": form['search']})
            if employee:
                raise web.seeother('/employees/' + employee['jira_uname'])
        else:

            raise web.seeother('/employees')

class ExportEmployeesCSV(CorpBase):
    @authenticated
    def GET(self, pp):
        print "GET ExportEmployeesCSV"

        employees = corpdb.employees.find({"employee_status" : {"$ne" : "Former"}}).sort("last_name", pymongo.ASCENDING)

        employees_csv = []
        headers = ["last name","first name", "title", "jira username", "office", "phone", "primary email", "team(s)"]

        for employee in employees:
            row = []
            row.append(employee['last_name'])
            row.append(employee['first_name'])
            row.append(employee['title'])
            row.append(employee['jira_uname'])
            row.append(employee['office'])
            row.append(employee['primary_phone'])
            row.append(employee_model.primary_email(employee))
            teams = map(lambda team: team["name"], employee_model.get_teams(employee).values())
            row.append(", ".join(teams))
            employees_csv.append(row)

        web.header('Content-type', 'text/csv')
        web.header('Content-disposition', "attachment; filename=employees.csv")

        csv_file = StringIO.StringIO()
        writer = csv.writer(csv_file,quoting=csv.QUOTE_ALL)
        writer.writerow(headers)
        writer.writerows(employees_csv)

        csv_file.write('\n')
        csv_file.seek(0)

        return csv_file


class ExportEmployeesSkillsCSV(CorpBase):
    @authenticated
    @require_admin_or_manager
    def GET(self, pp):
        print "GET ExportEmployeesSkillsCSV"

        employees = corpdb.employees.find({"employee_status" : {"$ne" : "Former"}}).sort("last_name", pymongo.ASCENDING)

        employees_csv = []
        headers = ["last name","first name", "title", "email", "office"]

        for skill_group in corpdb.skill_groups.find():
            for skill in corpdb.skills.find({"groups":ObjectId(skill_group['_id'])}).sort("name", pymongo.ASCENDING):
                headers.append(skill['name'])

        for employee in employees:
            row = []
            row.append(employee['last_name'])
            row.append(employee['first_name'])
            row.append(employee['title'])
            row.append(employee_model.primary_email(employee))
            row.append(employee['office'])
            employees_csv.append(row)
            for skill_group in corpdb.skill_groups.find():
                for skill in corpdb.skills.find({"groups":ObjectId(skill_group['_id'])}).sort("name", pymongo.ASCENDING):
                    if str(skill['_id']) in employee['skills']:
                        row.append(employee['skills'][str(skill['_id'])])
                    else:
                        row.append('')
	
        web.header('Content-type', 'text/csv')
        web.header('Content-disposition', "attachment; filename=skillmatrix.csv")

        csv_file = StringIO.StringIO()
        writer = csv.writer(csv_file,quoting=csv.QUOTE_ALL)
        writer.writerow(headers)
        writer.writerows(employees_csv)

        csv_file.write('\n')
        csv_file.seek(0)

        return csv_file


class Employees(CorpBase):
    @authenticated
    #MEMBER SHOW PAGE
    def GET(self, pp, *args):
        print "GET employees"
        try:
            pp['employee'] = corpdb.employees.find_one({"jira_uname": args[0]})
        except:
            pp['employee'] = ""

        if pp['employee']:
            pp['display_keys'] = employee_model.display_keys()
            pp['no_show'] = employee_model.no_show()

            # Set up hmac hash in order to request latest DUs
            pp['client_id'] = "test"
            key = "test"
            request_data = pp['employee']['jira_uname'] + pp['client_id']
            h = hmac.new(key, request_data, hashlib.sha256)
            pp['hmac'] = h.hexdigest()

            # Construct a list of links to team pages
            pp['teams'] = []
            if 'team_ids' in pp['employee']:
                teams = corpdb.teams.find({"_id" : {"$in": pp['employee']['team_ids'] }})
                for team in teams:
	                link = "<a href='/teams/{0}'>{1}</a>".format(team["_id"], team['name'])
	                pp['teams'].append(link)

            pp['managers'] = employee_model.get_managers(pp['employee'])
            pp['manager_hierarchies'] = employee_model.get_manager_hierarchies(pp['employee'])

            # Construct a list of skill names
            pp['skills'] = {}
            pp['top_tech_skills'] = []
            if 'skills' in pp['employee']:
                # TODO: use $in
                for skill_id in pp['employee']['skills']:
                    skill_groups = corpdb.skills.find_one(ObjectId(skill_id))['groups']
                    # adds the skill to group buckets
                    for group_id in skill_groups:
                        group_name = corpdb.skill_groups.find_one(group_id)['name']
                        # sets up the top_tech_skills field
                        if (pp['employee']['skills'][skill_id] == 5) and (group_name != "HUMAN LANGUAGE") and (pp['top_tech_skills'].__len__() < 4) :
                            pp['top_tech_skills'].append(corpdb.skills.find_one(ObjectId(skill_id)))
                        if group_name not in pp['skills']:
                            pp['skills'][group_name] = []
                        pp['skills'][group_name].append( ( corpdb.skills.find_one(ObjectId(skill_id)), pp['employee']['skills'][skill_id]) )
                #sort each skill group's skills by number of stars.
                for skill_group in pp['skills']:
                    pp['skills'][skill_group] = sorted(pp['skills'][skill_group], key=lambda skill: -skill[1])

            # set up hash to get gravatar
            pp['employee']['email'] = employee_model.primary_email(pp['employee'])
            if pp['employee']['email']:
                 pp['gravatar_hash'] = md5(pp['employee']['email'].strip())
            else:
                 pp['gravatar_hash'] = ""

            pp['employee']['email_addresses'] = ""
            pp['employee']['email_addresses'] = ", ".join(pp['employee']['email_addresses'] )

            # Can current user edit the requested employee's profile?  
            # Current user is request user, current user is requested user's manager, current user is admin
            pp['current_user_roles'] = current_user_roles(pp)
            requested_employees_managers = map(lambda manager: manager['jira_uname'], employee_model.get_managers(pp['employee']))
            if pp['user'] in requested_employees_managers or pp['user'] == pp['employee']['jira_uname'] or "admin" in pp['current_user_roles']:
                pp['can_edit'] = True
            else:
                pp['can_edit'] = False
            
            return env.get_template('employees/employees/show.html').render(pp=pp)
            
        else:
            raise web.seeother('/employees')


class ExportEmployeeVcard(CorpBase):
    #export an exmployee's vcard
    @authenticated
    def GET(self, pp, *args):
        print "GET ExportEmployeeVcard"
        jira_uname = args[0]
        employee = corpdb.employees.find_one({"jira_uname": jira_uname})
        if employee is None:
            raise web.seeother('/employees')
        else:
            vcard_str = employee_model.to_vcard(employee)
            web.header('Content-type', 'text/x-vcard')
            web.header('Content-disposition', "attachment; filename=contact.vcf")
            return vcard_str

class EditEmployee(CorpBase):
    #DISPLAY EDIT PAGE
    @authenticated
    @require_manager_admin_or_self
    def GET(self, pp, *args):
        print "GET EditEmployee"
        jira_uname = args[0]
        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        if pp['employee'] is None:
            raise web.seeother('/employees')
        else:
            pp['offices'] = corpdb.employees.distinct("office")
            pp['statuses'] = list(set(corpdb.employees.distinct("employee_status")+["Former"]))
            pp['team_members'] = corpdb.employees.find({"_id": {"$ne": pp['employee']['_id']}})
            pp['primary_email'] = employee_model.primary_email(pp['employee'])

            pp['extra_fields'] = []
            for n in pp['employee'].keys():
                if n not in employee_model.editable_keys() and n not in employee_model.no_show():
                    pp['extra_fields'].append(n)
            #print "extra fields: ", pp['extra_fields']
 
            if pp['employee']['jira_uname'] == pp['user']:
                pp['is_current_user'] = True
            else:
                pp['is_current_user'] = False

            pp['current_user_roles'] = current_user_roles(pp)

            # set up hash to get gravatar
            pp['primary_email'] = employee_model.primary_email(pp['employee'])
            if pp['primary_email']:
                pp['gravatar_hash'] = md5(pp['primary_email'].strip())
            else:
                pp['gravatar_hash'] = ""

            # format the dates (get rid of hour/min/seconds values)
            try:
                pp['birthday'] = pp['employee']["birthday"].strftime("%d-%m-%Y")
            except:
                pp['birthday'] = ""

            try:
                pp['start_date'] = pp['employee']["start_date"].strftime("%d-%m-%Y")
            except:
                pp['start_date'] = ""

            #set up dict for skills and their groups
            pp['skill_groups'] = {}
            mongodb_skill_group = corpdb.skill_groups.find_one({"name":"MONGODB"})
            prog_skill_group = corpdb.skill_groups.find_one({"name":"PROGRAMMING"})
            human_lang_skill_group = corpdb.skill_groups.find_one({"name":"HUMAN LANGUAGE"})
            specialty_skill_group = corpdb.skill_groups.find_one({"name":"SPECIALTY"})
            general_skill_group = corpdb.skill_groups.find_one({"name":"GENERAL"})
            
            if mongodb_skill_group:
                pp['skill_groups']['MONGODB'] = []
                for skill in corpdb.skills.find({"groups": mongodb_skill_group["_id"]}).sort("name", pymongo.ASCENDING):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['MONGODB'].append(skill)
            
            if prog_skill_group:
                pp['skill_groups']['PROGRAMMING'] = []
                for skill in corpdb.skills.find({"groups": prog_skill_group["_id"]}).sort("name", pymongo.ASCENDING):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['PROGRAMMING'].append(skill)
            
            if human_lang_skill_group:
                pp['skill_groups']['HUMAN LANG'] = []
                for skill in corpdb.skills.find({"groups": human_lang_skill_group["_id"]}).sort("name", pymongo.ASCENDING):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['HUMAN LANG'].append(skill)
            
            if specialty_skill_group:
                pp['skill_groups']['SPECIALTY'] = []
                for skill in corpdb.skills.find({"groups": specialty_skill_group["_id"]}).sort("name", pymongo.ASCENDING):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['SPECIALTY'].append(skill)
            
            if general_skill_group:
                pp['skill_groups']['GENERAL'] = []
                for skill in corpdb.skills.find({"groups": general_skill_group["_id"]}).sort("name", pymongo.ASCENDING):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['GENERAL'].append(skill)
            
            pp['teams'] = corpdb.teams.find().sort("name", pymongo.ASCENDING)                
           
            return env.get_template('employees/employees/edit.html').render(pp=pp)

    #EDIT FORM SUBMITS TO HERE
    @authenticated
    @require_manager_admin_or_self
    def POST(self, pp, *args): # maybe employee id?
        "POST EditEmployee"
        form = web.input(managing_ids=[], skills_MONGODB=[], skills_PROG=[], skills_HUMAN=[], skills_SPECIALTY=[], skills_GENERAL=[], team_ids=[])
        print form
        jira_uname = args[0]
        employee = corpdb.employees.find_one({"jira_uname": jira_uname})

        pp['current_user_roles'] = current_user_roles(pp)

        #a first name and last name must be entered
        if len(form['first_name']) > 0 and len(form['last_name']) > 0:

            for n in form.keys():
                if n.split("_")[0] == "skills":
                    for skill in form[n]:
                        if 'skills' not in employee:
                            employee['skills'] = {}
                        if skill not in employee['skills']:
                            employee["skills"][skill] = 0

                elif n == "managing_ids":
                    for employee_id in form["managing_ids"]:
                        managed_employee = corpdb.employees.find_one({"_id": ObjectId(employee_id)})
                        if managed_employee:
                            if "manager_ids" not in managed_employee.keys():
                                managed_employee["manager_ids"] = []
                            if employee['_id'] not in managed_employee["manager_ids"]:
                                managed_employee["manager_ids"].append(employee['_id'])
                                corpdb.employees.save(managed_employee)
                elif n == "team_ids":
                    if "admin" in pp['current_user_roles'] or "manager" in pp['current_user_roles']:
                        employee['team_ids'] = map(lambda team_id: ObjectId(team_id), form['team_ids'])
                else:
                    employee[n] = form[n]

            #remove skills
            if employee['skills']:
                for skill in employee['skills'].keys():
                    if skill not in form['skills_MONGODB'] and skill not in form['skills_PROG'] and skill not in form['skills_HUMAN'] and skill not in form['skills_SPECIALTY'] and skill not in form['skills_GENERAL']:
                        del employee['skills'][skill]

            #remove managed_employees
            # TODO: use $pull instead
            managed_employees = corpdb.employees.find({"manager_ids": ObjectId(employee['_id'])})
            for managed_employee in managed_employees:
                if managed_employee['_id'] not in form['managing_ids']:
                    managed_employee['manager_ids'].remove(employee['_id'])

            # handle date
            employee['start_date'] = employee_model.generate_date(form['start_date'])
            employee['birthday'] = employee_model.generate_date(form['birthday'])
            corpdb.employees.save(employee)
            raise web.seeother('/employees/' + employee['jira_uname'])

        # first name or last name (or both) is blank.  Render edit page with error message.
        else:
            pp['employee'] = employee
            pp['offices'] = corpdb.employees.distinct("office")
            pp['statuses'] = list(set(corpdb.employees.distinct("employee_status")+["Former"]))
            pp['team_members'] = corpdb.employees.find({"_id": {"$ne": pp['employee']['_id']}})
            pp['primary_email'] = employee_model.primary_email(pp['employee'])

            if pp['employee']['jira_uname'] == pp['user']:
                pp['is_current_user'] = True
            else:
                pp['is_current_user'] = False


            pp['extra_fields'] = []
            for n in pp['employee'].keys():
                if n not in employee_model.editable_keys() and n not in employee_model.no_show():
                    pp['extra_fields'].append(n)
            #print "extra fields: ", pp['extra_fields']

            # set up hash to get gravatar
            pp['primary_email'] = employee_model.primary_email(pp['employee'])
            if pp['primary_email']:
                pp['gravatar_hash'] = md5(pp['primary_email'].strip())
            else:
                pp['gravatar_hash'] = ""

            # format the dates (i.e. get rid of the time)
            try:
                pp['birthday'] = pp['employee']["birthday"].strftime("%d-%m-%Y")
            except:
                pp['birthday'] = ""

            try:
                pp['start_date'] = pp['employee']["start_date"].strftime("%d-%m-%Y")
            except:
                pp['start_date'] = ""

            #set up dict for skills and their groups
            pp['skill_groups'] = {}
            mongodb_skill_group = corpdb.skill_groups.find_one({"name":"MONGODB"})
            prog_skill_group = corpdb.skill_groups.find_one({"name":"PROGRAMMING"})
            human_lang_skill_group = corpdb.skill_groups.find_one({"name":"HUMAN LANGUAGE"})
            specialty_skill_group = corpdb.skill_groups.find_one({"name":"SPECIALTY"})
            general_skill_group = corpdb.skill_groups.find_one({"name":"GENERAL"})
            
            if mongodb_skill_group:
                pp['skill_groups']['MONGODB'] = []
                for skill in corpdb.skills.find({"groups": mongodb_skill_group["_id"]}).sort("name", pymongo.ASCENDING):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['MONGODB'].append(skill)
            
            if prog_skill_group:
                pp['skill_groups']['PROGRAMMING'] = []
                for skill in corpdb.skills.find({"groups": prog_skill_group["_id"]}).sort("name", pymongo.ASCENDING):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['PROGRAMMING'].append(skill)
            
            if human_lang_skill_group:
                pp['skill_groups']['HUMAN LANG'] = []
                for skill in corpdb.skills.find({"groups": human_lang_skill_group["_id"]}).sort("name", pymongo.ASCENDING):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['HUMAN LANG'].append(skill)
            
            if specialty_skill_group:
                pp['skill_groups']['SPECIALTY'] = []
                for skill in corpdb.skills.find({"groups": specialty_skill_group["_id"]}).sort("name", pymongo.ASCENDING):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['SPECIALTY'].append(skill)
            
            if general_skill_group:
                pp['skill_groups']['GENERAL'] = []
                for skill in corpdb.skills.find({"groups": general_skill_group["_id"]}).sort("name", pymongo.ASCENDING):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['GENERAL'].append(skill)
            
            pp['teams'] = corpdb.teams.find().sort("name", pymongo.ASCENDING)
            
            pp['error_message'] = "You must have values for first and last name."
            return env.get_template('employees/employees/edit.html').render(pp=pp)


class DeleteEmployee(CorpBase):
    @authenticated
    @require_admin
    def POST(self, pp, *args):
        print "POST DeleteEmployee"
        jira_username = args[0]
        employee = corpdb.employees.find_one({"jira_uname": jira_username})
        if employee:
            corpdb.employees.update({"manager_ids": ObjectId(employee["_id"])}, {"$pull" : {"manager_ids" : ObjectId(employee["_id"])} }, upsert=False, multi=True )
            corpdb.employees.remove(employee['_id'])
        raise web.seeother('/employees')


class RateSkills(CorpBase):
    @authenticated
    @require_manager_admin_or_self
    def GET(self, pp, *args):
        print "GET RateSkills"
        jira_uname = args[0]
        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        if pp['employee'] is None or "skills" not in pp['employee'].keys():
            raise web.seeother('/employees')
        else:
            pp['primary_email'] = employee_model.primary_email(pp['employee'])
            pp['skills'] = {}
            pp['levels'] = ['', 'Describe to Fellow Engineer', 'Discuss with Customer', 'Fix Bugs in Code', 'Add Improvements', 'Architect Features']
            pp['human_lang_levels'] = ['', 'Interpret Written and/or Orally', 'Conversational', 'Presentational']
            
            # Current user is requested user's manager, current user is admin
            pp['current_user_roles'] = current_user_roles(pp)
            requested_employees_managers = map(lambda manager: manager['jira_uname'], employee_model.get_managers(pp['employee']))
            if pp['user'] in requested_employees_managers or "admin" in pp['current_user_roles']:
                pp['can_rate'] = True
            else:
                pp['can_rate'] = False

            pp['locked_skillgroup_names'] = [ "PROGRAMMING", "MONGODB", "SPECIALTY", "GENERAL" ]
                
            # separate skills in skill_groups
            for skill_id in pp['employee']['skills']:
                skill_groups = corpdb.skills.find_one(ObjectId(skill_id))['groups']
                # only want a skill to show up in one group bucket
                group_id = skill_groups[0]
                group_name = corpdb.skill_groups.find_one(group_id)['name']
                if group_name not in pp['skills']:
                    pp['skills'][group_name] = {}
                pp['skills'][group_name][skill_id] = corpdb.skills.find_one(ObjectId(skill_id))

            return env.get_template('employees/employees/rate_skills.html').render(pp=pp)

    @authenticated
    @require_manager_admin_or_self
    def POST(self, pp, *args):
        print "POST RateSkills"
        form = web.input()
        jira_uname = args[0]
        print form
        employee = corpdb.employees.find_one({"jira_uname": jira_uname})
        if employee:
            for skill_id in employee['skills'].keys():
                if skill_id in form.keys():
                    employee['skills'][skill_id] = int(form[skill_id])
            corpdb.employees.save(employee)
            raise web.seeother('/employees/' + employee['jira_uname'])
        else:
            raise web.seeother('/employees')


class NewEmployee(CorpBase):
    @authenticated
    @require_admin
    def GET(self, pp):
        print "GET NewEmployee"
        pp['teams'] = corpdb.teams.find().sort("name", pymongo.ASCENDING)
        return env.get_template('employees/employees/new.html').render(pp=pp)

    @authenticated
    @require_admin
    def POST(self, pp):
        print "POST NewEmployee"
        form = web.input()
        print form
        if len(form['first_name']) > 0 and len(form['last_name']) > 0 and len(form['email_address']) > 0 and len(form['jira_uname']) and len(form['team_id']):
            jira_uname = form['jira_uname'].lower()
            # make sure there are no other users with this email address
            employee = corpdb.employees.find_one({"jira_uname": jira_uname})
            print "employee already exists: ", employee
            if not employee:
                employee = {'first_name': form['first_name'],
                'last_name': form['last_name'],
                'email_addresses': [form['email_address']],
                'jira_uname': jira_uname,
                'team_ids':[ObjectId(form['team_id'])],
                'roles': ['employee'],
                'skills': {}
                }
                try:
                    id = corpdb.employees.insert(employee, safe=True)
                except:
                    print "employee not inserted"

                if id:
                    raise web.seeother('/employees/' + jira_uname + "/edit")
                else:
                    raise web.seeother('/employees')
            # employee with jira name found
            else:
                raise web.seeother('/employees/' + jira_uname)
        else:
            raise web.seeother('/employees')


class EditEmailAddress(CorpBase):
    @authenticated
    @require_current_user
    def GET(self, pp, *args):
        print "GET EditEmailAddress"
        jira_uname = args[0]
        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        if pp['employee'] is not None:
            return env.get_template('employees/employees/edit_email_addresses.html').render(pp=pp)
        else:
            raise web.seeother('/employees/')

    @authenticated
    @require_current_user
    def POST(self, pp, *args):
        print "POST EditEmailAddress"
        form = web.input()
        print form
        jira_uname = args[0]
        employee = corpdb.employees.find_one({"jira_uname": jira_uname})
        if employee is not None:
            if "_method" in form.keys() and form["_method"] == "delete":
                #Remove the email address if the employee has more than one. Otherwise don't delete the email address.
                if len(employee["email_addresses"]) > 1:
                    employee["email_addresses"].remove(form["email_address"])
                    corpdb.employees.save(employee)
            else:
                #If the employee doesn't have any email addresses yet, set up the email address list.
                if "email_addresses" not in employee.keys():
                    employee["email_addresses"] = []
                # check to make sure the email address isn't already saved
                if form['email_address'] not in employee["email_addresses"]:
                    employee["email_addresses"].append(form['email_address'])
                    corpdb.employees.save(employee)
            raise web.seeother('/employees/' + employee['jira_uname'] + "/edit")
        #employee not found
        else:
            raise web.seeother('/employees/')


class NewEmployeeField(CorpBase):
    @authenticated
    @require_manager_admin_or_self
    def GET(self, pp, *args):
        print "GET NewEmployeeField"
        jira_uname = args[0]
        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        if pp['employee'] is not None:
            return env.get_template('employees/employees/new_field.html').render(pp=pp)
        else:
            raise web.seeother('/employees/')

    @authenticated
    @require_manager_admin_or_self
    def POST(self, pp, *args):
        print "POST NewEmployeeField"
        form = web.input()
        jira_uname = args[0]
        employee = corpdb.employees.find_one({"jira_uname": jira_uname})
        if employee:
            employee[form['field_name'].capitalize()] = ""
            corpdb.employees.save(employee)
            raise web.seeother('/employees/' + employee['jira_uname'] + "/edit")
        else:
            raise web.seeother('/employees/')


class EditEmployeeImage(CorpBase):
    @authenticated
    @require_current_user
    def GET(self, pp, *args):
        print "GET EditEmployeeImage"
        jira_uname = args[0]
        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        pp['employee_email_address'] = employee_model.primary_email(pp['employee'])
        pp['email_hash'] = employee_model.email_hash(pp['employee'])
        if pp['employee'] is not None:
            return env.get_template('employees/employees/edit_image.html').render(pp=pp)
        else:
            raise web.seeother('/employees/')

    @authenticated
    @require_current_user
    def POST(self, pp, *args):
        print "POST EditEmployeeImage"
        jira_uname = args[0]
        image = web.input(image_file={})['image_file']
        if image.value != "":
            gfs = gridfs.GridFS(corpdb)
            gfs.put(image.value, filename=jira_uname)

        employee = corpdb.employees.find_one({"jira_uname": jira_uname})
        if employee:
            raise web.seeother('/employees/' + employee['jira_uname'] + "/edit")
        else:
            raise web.seeother('/employees/')


class DeleteEmployeeImage(CorpBase):
    @authenticated
    @require_current_user
    def POST(self, pp, *args):
        print "POST DeleteEmployeeImage"
        form = web.input()
        jira_uname = args[0]        
        gfs = gridfs.GridFS(corpdb)

        while gfs.exists({"filename" : jira_uname }):
            file = gfs.get_last_version(filename=jira_uname)
            gfs.delete(file._id)

        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        raise web.seeother('/employees/' + str(pp['employee']['jira_uname']) + "/edit")


class ExportAllEmployeesVcard(CorpBase):
    @authenticated
    def GET(self, pp):
        print "GET ExportAllEmployeesVcard"
        vcard_str = ""

        for employee in corpdb.employees.find({"employee_status" : {"$ne" : "Former"}}).sort("last_name", pymongo.ASCENDING):
            try:
                vcard = employee_model.to_vcard(employee)
            except:
                vcard = ""
            if vcard:
                vcard_str += vcard + "\n"
        web.header('Content-type', 'text/x-vcard')
        web.header('Content-disposition', "attachment; filename=contact.vcf")
        return vcard_str

############################################################
# Org Structure
############################################################
class OrgStructure(CorpBase):
    @authenticated
    def GET(self, pp):
        print "GET OrgStructure"
        pp['org_structure'] = employee_model.org_structure()
        pp['teams'] = {}

        # Populate a dict of members for each team
        for team in corpdb.teams.find():
            pp['teams'][team['name']] = {}
            for employee in corpdb.employees.find({"team_ids": ObjectId(team['_id']), "employee_status" : {"$ne" : "Former"}}):
                if employee['first_name'] and employee['last_name'] :
                    pp['teams'][team['name']][str(employee['jira_uname'])] = str(employee['first_name'] + " " + employee['last_name'])

        pp['org_chart'] = employee_model.org_structure_list()

        return env.get_template('employees/employees/org_chart_jquery.html').render(pp=pp)

############################################################
# Org Structure List
############################################################
class OrgStructureList(CorpBase):
    @authenticated
    def GET(self, pp):
        print "GET OrgStructure"
        pp['org_structure'] = employee_model.org_structure()
        pp['teams'] = {}

        # Populate a dict of members for each team
        for team in corpdb.teams.find():
            pp['teams'][team['name']] = {}
            for employee in corpdb.employees.find({"team_ids": ObjectId(team['_id']), "employee_status" : {"$ne" : "Former"}}):
                if employee['first_name'] and employee['last_name'] :
                    pp['teams'][team['name']][str(employee['jira_uname'])] = str(employee['first_name'] + " " + employee['last_name'])

        pp['org_chart'] = employee_model.org_structure_list()

        return env.get_template('employees/employees/org_chart_list.html').render(pp=pp)


############################################################
# Profile Images
############################################################
class ProfileImage(CorpBase):
    @authenticated
    def GET(self, pp, *args):
        print "GET ProfileImage"
        jira_uname = args[0]
        gfs = gridfs.GridFS(corpdb)
        try:
            f = gfs.get_last_version(filename=jira_uname)
        except:
            f = ""
        if not f:
            return
        web.header('Content-type', 'image/jpeg')
        return f.read()


############################################################
# Teams
############################################################
class Teams(CorpBase):
    @authenticated
    def GET(self, pp, *args):
        print "GET Teams"
        pp['current_user_roles'] = current_user_roles(pp)
        try:
            team_id = args[0]
        except:
            team_id = ""
        if team_id:
            pp['team'] = corpdb.teams.find_one(ObjectId(team_id))

            if pp['team']:
                pp['team_members'] = corpdb.employees.find({"team_ids": pp['team']['_id'], "employee_status" : {"$ne" : "Former"}}).sort("name", pymongo.ASCENDING)
                if "team_lead_ids" in pp['team']:
                    pp['team_leads'] = corpdb.employees.find({ "_id" : { "$in" : pp['team']['team_lead_ids']}})
                if "project_manager_ids" in pp['team']:
                    pp['project_managers'] = corpdb.employees.find({ "_id" : { "$in" : pp['team']['project_manager_ids']}})
                pp['managed_teams'] = corpdb.teams.find({"managing_team_ids": pp['team']['_id']})
                if "managing_team_ids" in pp['team']:
                    pp['managing_teams'] = corpdb.teams.find({"_id" : { "$in" : pp['team']['managing_team_ids']}})
                return env.get_template('employees/teams/show.html').render(pp=pp)
            else:
                print "team not found"
                raise web.seeother('/teams')
        else:
            pp['teams'] = corpdb.teams.find().sort("name", pymongo.ASCENDING)
            return env.get_template('employees/teams/index.html').render(pp=pp)

    @authenticated
    def POST(self, pp):
        print "POST Teams index (search)"
        form = web.input()
        if 'search' in form.keys():
            team = corpdb.teams.find_one({"_id" : ObjectId(form['search'])})
            if team is None:
		        raise web.seeother('/teams')
            else:
		        print "team found"
		        raise web.seeother('/teams/' + str(team['_id']))		
        else:
            raise web.seeother('/teams')


class EditTeam(CorpBase):
    @authenticated
    @require_admin
    def GET(self, pp, *args):
        print "GET EditTeam"
        team_id = args[0]
        pp['team'] = corpdb.teams.find_one(ObjectId(team_id))

        if pp['team'] is None:
            print "team not found"
            raise web.seeother('/teams')
        else:
            pp['teams'] = corpdb.teams.find({"_id": {"$ne": pp['team']['_id']}}).sort("name", pymongo.ASCENDING)
            pp['employees'] = corpdb.employees.find({"employee_status": {"$ne": "Former"}}).sort("name", pymongo.ASCENDING)
            pp['employees2'] = corpdb.employees.find({"employee_status": {"$ne": "Former"}}).sort("name", pymongo.ASCENDING)
            return env.get_template('employees/teams/edit.html').render(pp=pp)

    @authenticated
    @require_admin
    def POST(self, pp, *args):
        print "POST EditTeam"
        form = web.input(managing_team_ids=[], team_lead_ids=[], project_manager_ids=[])
        print form
        team_id = args[0]
        pp['team'] = corpdb.teams.find_one(ObjectId(team_id))

        # Name cannot be blank.
        if len(form['name']) > 0:
            pp['team']['name'] = form['name'].capitalize()
            pp['team']['managing_team_ids'] = map(lambda id: ObjectId(id), form['managing_team_ids'])
            pp['team']['project_manager_ids'] = map(lambda id: ObjectId(id), form['project_manager_ids'])
            # Must have a team lead.
            if len(form['team_lead_ids']) > 0:
                pp['team']['team_lead_ids'] = map(lambda id: ObjectId(id), form['team_lead_ids'])
                corpdb.teams.save(pp['team'])
                raise web.seeother('/teams/' + str(pp['team']['_id']))
            else:
                pp['teams'] = corpdb.teams.find({"_id": {"$ne": pp['team']['_id']}}).sort("name", pymongo.ASCENDING)
                pp['employees'] = corpdb.employees.find({"employee_status": {"$ne": "Former"}}).sort("name", pymongo.ASCENDING)
                pp['employees2'] = corpdb.employees.find({"employee_status": {"$ne": "Former"}}).sort("name", pymongo.ASCENDING)
                pp['error_message'] = "You must have a team lead."
                return env.get_template('employees/teams/edit.html').render(pp=pp)
        else:
            raise web.seeother('/teams')


class NewTeam(CorpBase):
    @authenticated
    @require_admin
    def GET(self, pp):
        print "GET NewTeam"
        return env.get_template('employees/teams/new.html').render(pp=pp)

    @authenticated
    @require_admin
    def POST(self, pp):
        print "POST NewTeam"
        form = web.input()
        if len(form['name']) > 0:
            try:
                 team = {'name': form['name'].capitalize() }
                 corpdb.teams.insert(team)
            except:
                print "team not inserted"
            if team:
                raise web.seeother('/teams/' + str(team['_id']) + "/edit")
            else:
                raise web.seeother('/teams')
        else:
            raise web.seeother('/teams')


class DeleteTeam(CorpBase):
    @authenticated
    @require_admin
    def POST(self, pp, *args):
        print "POST DeleteTeam"
        team_id = args[0]
        team = corpdb.teams.find_one({"_id": ObjectId(team_id)})
        if team:
            corpdb.employees.update({"team_ids" : team['_id']}, {"$pull": {"team_ids": team['_id'] }}, upsert=False, multi=True)
            corpdb.teams.update({"managing_team_ids" : team['_id']}, {"$pull": {"managing_team_ids": team['_id']}}, upsert=False, multi=True)
            corpdb.teams.remove(team['_id'])
        raise web.seeother('/teams')


############################################################
# Skills
############################################################
class Skills(CorpBase):
    @authenticated
    def GET(self, pp, *args):
        print "GET Skills"
        try:
            skill_id = args[0]
        except:
            skill_id = ""
        current_user = corpdb.employees.find_one({"jira_uname" : pp['user']})
        pp['current_user_roles'] = current_user_roles(pp)

        if skill_id:
            pp['skill'] = corpdb.skills.find_one(ObjectId(skill_id))

            if pp['skill']:
                # Change the ObjectId to a string to be used in the employee skills embedded doc
                pp['skill']['_id'] = str(pp['skill']['_id'])
                pp['skill']['group_names'] = map(lambda skill_group: skill_group["name"], corpdb.skill_groups.find({"_id": { "$in" : pp['skill']['groups']}}))
                pp['skill_groups'] = []
                pp['employees'] = []
                pp['skill_groups'] = corpdb.skill_groups.find({"_id" : { "$in" : pp['skill']['groups']}})
                for x in range(1, 6):  
                    pp['employees'].insert(x-1, corpdb.employees.find({"skills."+ str(pp['skill']['_id']): x, "employee_status" : {"$ne": "Former"}}))
                # Sort employees by their skill level
#pp['employees'] = sorted(pp['employees'], key=lambda employee: -employee['skills'][str(pp['skill']['_id'])])
                return env.get_template('employees/skills/show.html').render(pp=pp)

            else:
                print "skill not found"
                raise web.seeother('/skills')
        else:
            
            pp['skills'] = corpdb.skills.find().sort("name", pymongo.ASCENDING)
            return env.get_template('employees/skills/index.html').render(pp=pp)

    @authenticated
    def POST(self, pp, *args):
        print "POST Skills index (search)"
        form = web.input()
        pp['skill'] = corpdb.skills.find_one(ObjectId(form['search']))
        print pp['skill']
        if pp['skill'] is None:
            raise web.seeother('/skills')
        else:
            print "skill found"
            raise web.seeother('/skills/' + form['search'])


class EditSkill(CorpBase):
     @authenticated
     @require_admin_or_manager
     def GET(self, pp, *args):
         print "GET EditSkill"
         skill_id = args[0]
         pp['skill'] = corpdb.skills.find_one(ObjectId(skill_id))
         if pp['skill']:
             pp['skill_groups'] = corpdb.skill_groups.find().sort("name", pymongo.ASCENDING)
             return env.get_template('employees/skills/edit.html').render(pp=pp)
         else:
             raise web.seeother('/skills')

     @authenticated
     @require_admin_or_manager
     def POST(self, pp, *args):
         print "POST EditSkill"
         form = web.input(skill_groups=[])
         print form
         skill_id = args[0]
         pp['skill'] = corpdb.skills.find_one(ObjectId(skill_id))
         #Name cannot be blank in order for this skill to be saved
         if len(form['name']) > 0:
             # Only save the name if it's unique TODO: use unique index on name and try/except instead
             if corpdb.skills.find({"name": form['name'].upper() }).count() == 0:
                 pp['skill']['name'] = form['name'].upper()
             # Group name is blank. Render edit page with error message.
             if len(form['skill_groups']) == 0:
                pp['name'] = form['name']
                pp['skill_groups'] = corpdb.skill_groups.find().sort("name", pymongo.ASCENDING)
                pp['error_message'] = "You must have a group for the skill."
                return env.get_template('employees/skills/edit.html').render(pp=pp)
             # Save the skill group ids
             pp['skill']['groups'] = map(lambda skill_group_id: ObjectId(skill_group_id), form['skill_groups'])
             corpdb.skills.save(pp['skill'])
             raise web.seeother('/skills/' + str(pp['skill']['_id']))
         raise web.seeother('/skills')


class NewSkill(CorpBase):
    @authenticated
    @require_admin
    def GET(self, pp):
        print "GET NewSkill"
        return env.get_template('employees/skills/new.html').render(pp=pp)

    @authenticated
    @require_admin
    def POST(self, pp):
        print "POST NewSkill"
        form = web.input()
        if len(form['name']) > 0:
            # make sure there are no other skills with this name TODO use unique index on name and try/except instead
            skill = corpdb.skills.find_one({"name": form['name'].upper()})
            if not skill:
                skill = {'name': form['name'].upper() }
                try:
                     objectid = corpdb.skills.insert(skill)
                except:
                     print "skill not inserted"
                if objectid:
                     raise web.seeother('/skills/' + str(objectid) + "/edit")
                else:
                     raise web.seeother('/skills')
            print "skill found"
            raise web.seeother('/skills/' + str(skill['_id']) + "/edit")
        raise web.seeother('/skills')

class DeleteSkill(CorpBase):
    @authenticated
    @require_admin
    def POST(self, pp, *args):
        print "POST DeleteSkill"
        skill_id = args[0]
        corpdb.employees.update({"skills."+ skill_id: {"$exists":True} }, {"$unset": {"skills."+ skill_id: 1}}, upsert=False, multi=True)
        corpdb.skills.remove(ObjectId(skill_id))
        raise web.seeother('/skills')


############################################################
# Skill Groups
############################################################
class SkillGroups(CorpBase):
    @authenticated
    def GET(self, pp, *args):
        print "GET SkillGroups"
        pp['current_user_roles'] = current_user_roles(pp)
        try:
            skill_group_id = args[0]
        except:
            skill_group_id = ""
        if skill_group_id:
            pp['skill_group'] = corpdb.skill_groups.find_one(ObjectId(skill_group_id))

            if pp['skill_group']:
	            pp['skills'] = []
                # TODO: use $in instead
	            for skill in corpdb.skills.find({"groups": pp['skill_group']['_id']}).sort("name", pymongo.ASCENDING):
	                pp['skills'].append(skill)
	            return env.get_template('employees/skill_groups/show.html').render(pp=pp)

            else:
                print "skill not found"
                raise web.seeother('/skillgroups')
        else:
            pp['skill_groups'] = corpdb.skill_groups.find().sort("name", pymongo.ASCENDING)
            return env.get_template('employees/skill_groups/index.html').render(pp=pp)

    @authenticated
    def POST(self, pp):
        print "POST SkillGroups index (search)"
        form = web.input()
        pp['skill_group'] = corpdb.skill_groups.find_one(ObjectId(form['search']))
        if pp['skill_group'] is None:
            raise web.seeother('/skillgroups')
        else:
            print "skillgroup found"
            raise web.seeother('/skillgroups/' + form['search'])


class EditSkillGroup(CorpBase):
     @authenticated
     @require_admin
     def GET(self, pp, *args):
         print "GET EditSkillGroup"
         skill_group_id = args[0]
         pp['skill_group'] = corpdb.skill_groups.find_one(ObjectId(skill_group_id))
         if pp['skill_group']:
             return env.get_template('employees/skill_groups/edit.html').render(pp=pp)
         else:
             raise web.seeother('/skillgroups')

     @authenticated
     @require_admin
     def POST(self, pp, *args):
         print "POST EditSkillGroup"
         form = web.input()
         print form
         skill_group_id = args[0]
         pp['skill_group'] = corpdb.skill_groups.find_one(ObjectId(skill_group_id))
         #Name cannot be blank
         if len(form['name']) > 0:
             if corpdb.skill_groups.find({"name": form['name']}).count() == 0:
                 pp['skill_group']['name'] = form['name']
                 corpdb.skill_groups.save(pp['skill_group'])
                 raise web.seeother('/skillgroups/' + str(pp['skill_group']['_id']))
         raise web.seeother('/skillgroups')

class NewSkillGroup(CorpBase):
    @authenticated
    @require_admin
    def GET(self, pp):
        print "GET NewSkillGroup"
        return env.get_template('employees/skill_groups/new.html').render(pp=pp)

    @authenticated
    @require_admin
    def POST(self, pp):
        print "POST NewSkillGroup"
        form = web.input()
        if len(form['name']) > 0:
            # make sure there are no other skill groups with this name
            skill_group = corpdb.skill_groups.find_one({"name": form['name'].upper()})
            if not skill_group:
                try:
                     objectid = corpdb.skill_groups.insert({'name': form['name'].upper() })
                except:
                     print "skill group not inserted"
                if objectid:
                     raise web.seeother('/skillgroups/' + str(objectid) + "/edit")
                else:
                     raise web.seeother('/skillgroups')
            
            print "skill group found"
            raise web.seeother('/skillgroups/' + str(skill_group['_id']) + "/edit")
        raise web.seeother('/skillgroups')

class DeleteSkillGroup(CorpBase):
    @authenticated
    @require_admin
    def POST(self, pp, *args):
        print "POST DeleteSkill"
        skill_group_id = ObjectId(args[0])
        corpdb.skills.update({"groups": skill_group_id}, {"$pull": {"groups": skill_group_id}}, upsert=False, multi=True)
        corpdb.skill_groups.remove(ObjectId(skill_group_id))
        raise web.seeother('/skillgroups')


############################################################
# Project Groups
############################################################
class ProjectGroups(CorpBase):
    @authenticated
   # TODO private and public project groups
    def GET(self, pp, *args):
        print "GET ProjectGroups"
        try:
            project_group_id = args[0]
        except:
            project_group_id = ""
        if project_group_id:
            pp['project_group'] = corpdb.project_groups.find_one(ObjectId(project_group_id))

            if pp['project_group']:
                pp['employees'] = []
                for member in pp['project_group']['members']:
                    employee = corpdb.employees.find_one(ObjectId(member['employee_id']))
                    if employee['employee_status'] != "Former":
                        employee['project_role'] = member['role']
                        pp['employees'].append(employee)
                return env.get_template('employees/project_groups/show.html').render(pp=pp)

            else:
                print "project group not found"
                raise web.seeother('/projectgroups')
        else:
            pp['project_groups'] = corpdb.project_groups.find().sort("name", pymongo.ASCENDING)
            pp['current_user_roles'] = ["manager"]
            return env.get_template('employees/project_groups/index.html').render(pp=pp)

    @authenticated
    # TODO private and public project groups
    def POST(self, pp):
        print "POST ProjectGroups index (search)"
        form = web.input()
        pp['project_group'] = corpdb.project_groups.find_one(ObjectId(form['search']))
        if pp['project_group'] is None:
            raise web.seeother('/projectgroups')
        else:
            raise web.seeother('/projectgroups/' + form['search'])

class NewProjectGroup(CorpBase):
    @authenticated
    # TODO private and public groups
    def GET(self, pp):
        print "GET NewProjectGroup"
        pp['employees'] = corpdb.employees.find({"employee_status" : {"$ne" : "Former"}}).sort("last_name", pymongo.ASCENDING)
        return env.get_template('employees/project_groups/new.html').render(pp=pp)

    @authenticated
    # TODO private and public groups
    def POST(self, pp):
        print "POST NewProjectGroup"
        form = web.input()
        if len(form['name']) > 0 and len(form['lead']) > 0:
            project_group = {'name': form['name'], 'members' : [{'employee_id': ObjectId(form['lead']), 'role': 'LEAD'}] }
            try:
                objectid = corpdb.project_groups.insert(project_group)
            except:
                print "project_group not inserted"
            if objectid:
                raise web.seeother('/projectgroups/' + str(objectid) + "/edit")
            else:
                raise web.seeother('/projectgroups')
        raise web.seeother('/projectgroups')


class EditProjectGroup(CorpBase):
     @authenticated
     # TODO who can edit?  LEAD?
     def GET(self, pp, *args):
         print "GET EditProjectGroup"
         project_group_id = args[0]
         pp['project_group'] = corpdb.project_groups.find_one(ObjectId(project_group_id))
         pp['roles'] = ['PRODUCT MANAGER','PROJECT MANAGER', 'DOCUMENTER','DEVELOPER','STAKEHOLDER', 'MEMBER']
         if pp['project_group']:
             pp['employees'] = []
             for member in pp['project_group']['members']:
                 employee = corpdb.employees.find_one(ObjectId(member['employee_id']))
                 if employee['employee_status'] != "Former":
                    employee['project_role'] = member['role']
                    pp['employees'].append(employee) 
             return env.get_template('employees/project_groups/edit.html').render(pp=pp)            
         else:
             raise web.seeother('/projectgroups')

     @authenticated
     # TODO who can edit? LEAD?
     def POST(self, pp, *args):
         print "POST EditProjectGroup"
         form = web.input()
         print form
         project_group_id = args[0]
         pp['project_group'] = corpdb.project_groups.find_one(ObjectId(project_group_id))
         #Name cannot be blank
         if form['name'] and len(form['name']) > 0:
             for attribute in form.keys():
                 if attribute.split("_")[0] == "employee" and attribute.split("_")[1] == "role":
                     selector = {"_id": ObjectId(project_group_id), "members.employee_id" : ObjectId(attribute.split("_")[2])}
                     update = {"$set": {"members.$.role": form[attribute]}} 
                 else:
                    selector = {"_id": ObjectId(project_group_id)}
                    update = {"$set": {attribute: form[attribute]}}
                 corpdb.project_groups.update(selector, update, upsert=False, multi=True)
             raise web.seeother('/projectgroups/' + str(pp['project_group']['_id']))
         raise web.seeother('/projectgroups')

class NewProjectGroupMember(CorpBase):
    @authenticated
    # TODO @require who?
    def GET(self, pp, *args):
        print "GET NewProjectGroupMember"
        pp['project_group_id'] = args[0]
        project_group = corpdb.project_groups.find_one(ObjectId(pp['project_group_id'] ))
        # get ids of all members of the project group
        member_ids = map(lambda member: member['employee_id'], project_group['members'])
        # only get the employees who are not already in the project group for dropdown
        pp['employees'] = corpdb.employees.find({"_id": {"$nin": member_ids}, "employee_status" : { "$ne" : "Former"}}).sort("last_name", pymongo.ASCENDING)
        pp['roles'] = ['PRODUCT MANAGER','PROJECT MANAGER', 'DOCUMENTER','DEVELOPER','STAKEHOLDER', 'MEMBER']
        return env.get_template('employees/project_groups/new_member.html').render(pp=pp)

    @authenticated
    # TODO @require who?
    def POST(self, pp, *args):
        print "POST NewProjectGroupMember"
        form = web.input()
        project_group_id = args[0]
        if len(form['member']) > 0 and len(form['role']) > 0:
            project_group = corpdb.project_groups.find_one(ObjectId(project_group_id))
            if project_group: # TODO: can't add a member who is already in the list
                project_group['members'].append({'employee_id':ObjectId(form['member']), 'role': form['role']})
                corpdb.project_groups.save(project_group)
        raise web.seeother('/projectgroups/' + project_group_id + '/edit')


class RemoveProjectGroupMember(CorpBase):
    @authenticated
    # TODO @require who?
    def POST(self, pp, *args):
        print "POST RemoveProjectGroupMember"
        project_group_id = args[0]
        corpdb.project_groups.remove(ObjectId(project_group_id))
        raise web.seeother('/projectgroups')


class DeleteProjectGroup(CorpBase):
    @authenticated
    # TODO @require who?
    def POST(self, pp, *args):
        print "POST DeleteProjectGroup"
        project_group_id = args[0]
        corpdb.project_groups.remove(ObjectId(project_group_id))
        raise web.seeother('/projectgroups')


############################################################
# Performance Reviews
############################################################
class PerformanceReviews(CorpBase):
    @authenticated
    def GET(self, pp, *args):
        print "GET PerformanceReviews"
        try:
            performance_review_id = args[0]
        except:
            performance_review_id = ""
        pp['current_user'] = corpdb.employees.find_one({"jira_uname" : pp['user']})
        pp['current_user_roles'] = current_user_roles(pp)

        if len(performance_review_id) > 0 :
            pp['performance_review'] = corpdb.performancereviews.find_one(ObjectId(performance_review_id))
            
            if pp['performance_review']:
                pp['manager'] = corpdb.employees.find_one(ObjectId(pp['performance_review']['manager_id']))
                pp['employee'] = corpdb.employees.find_one(ObjectId(pp['performance_review']['employee_id']))
                if str(pp['current_user']['_id']) == str(pp['performance_review']['employee_id']):
                    pp['view'] = "Employee"
                elif str(pp['current_user']['_id']) == str(pp['performance_review']['manager_id']):
                    pp['view'] = "Manager"
                else:
                    pp['view'] = "None"

                return env.get_template('employees/performancereviews/show.html').render(pp=pp)
            else:
                print "performance review not found"
                raise web.seeother('/performancereviews')
        else:
            pp['overdue_date'] = employee_model.add_days_to_date(datetime.now(), -1)
            pp['current_performancereview'] = corpdb.performancereviews.find_one( {"employee_id" : pp['current_user']['_id'], "status" : { "$ne" : "done"} } )
            pp['my_performancereviews'] = list( corpdb.performancereviews.find( {"employee_id" : pp['current_user']['_id'] }).sort("date", pymongo.DESCENDING) )
            pp['all_managing_reviews'] = list( corpdb.performancereviews.find( {"manager_id" : ObjectId(pp['current_user']['_id']) }).sort("name", pymongo.ASCENDING))
            if "manager" in pp['current_user_roles'] :
                pp['uncompleted_manager_reviews'] = list(corpdb.performancereviews.find( {"manager_id" : ObjectId(pp['current_user']['_id']), "status" : { "$ne" : "done"} } ).sort("name", pymongo.ASCENDING))
                pp['past_managing_performancereviews'] = list(corpdb.performancereviews.find( {"manager_id" : ObjectId(pp['current_user']['_id']), "status" : "done" }).sort("name", pymongo.ASCENDING))
            return env.get_template('employees/performancereviews/index.html').render(pp=pp)


    @authenticated
    def POST(self, pp, *args):
        print "POST PerformanceReview"
        form = web.input()
        if 'past_managee_reviews_search' in form.keys():
            raise web.seeother('/performancereviews/'+form['past_managee_reviews_search'])
        raise web.seeother('/performancereviews')

class EditPerformanceReview(CorpBase):

    @authenticated
    def GET(self, pp, *args):
        print "GET EditPerformanceReview"
        performance_review_id = args[0]
        pp['performance_review'] = corpdb.performancereviews.find_one(ObjectId(performance_review_id))
        if pp['performance_review'] is None:
            print "performance review not found"
            raise web.seeother('/performancereviews')

        # Which set of questions can the user see?
        pp['current_user'] = corpdb.employees.find_one({"jira_uname" : pp['user'] })
        if str(pp['current_user']['_id']) == str(pp['performance_review']['employee_id']):
            pp['view'] = "Employee"
        elif str(pp['current_user']['_id']) == str(pp['performance_review']['manager_id']):
            pp['view'] = "Manager"
        # Only employee or manager should be able to edit.
        else:
            print "unauthorized access to performance review edit page."
            raise web.seeother('/performancereviews')

        pp['employee'] = corpdb.employees.find_one({'_id': pp['performance_review']['employee_id']})
        return env.get_template('employees/performancereviews/edit.html').render(pp=pp)

    @authenticated
    def POST(self, pp, *args):
        print "POST EditPerformanceReview"
        form = web.input()
        print form
        performance_review_id = args[0]
        pp['performance_review'] = corpdb.performancereviews.find_one(ObjectId(performance_review_id))
        pp['current_user'] = corpdb.employees.find_one({"jira_uname" : pp['user']})
        # Save employee questions
        if str(pp['current_user']['_id']) == str(pp['performance_review']['employee_id']):
            for question in pp['performance_review']['employee_questions']:
                question['response'] = form[question['name']]
        # Save manager questions
        elif str(pp['current_user']['_id']) == str(pp['performance_review']['manager_id']):
            for question in pp['performance_review']['manager_questions']:
                question['response'] = form[question['name']]
        corpdb.performancereviews.save(pp['performance_review'])

        # Fields cannot be blank (must answer all questions)
        # TODO: make it so that you can fill out form partially and SAVE instead of SUBMIT
        for question in form:
            if len(form[question]) == 0 :
                pp['error_message'] = "You must answer all questions before submitting."
                pp['performance_review'] = corpdb.performancereviews.find_one(ObjectId(performance_review_id))
                pp['employee'] = corpdb.employees.find_one(ObjectId(pp['performance_review']['employee_id']))
                pp['current_user'] = corpdb.employees.find_one({"jira_uname" : pp['user'] })
                # Which set of questions can the user see?
                if str(pp['current_user']['_id']) == str(pp['performance_review']['employee_id']):
                    pp['view'] = "Employee"
                elif str(pp['current_user']['_id']) == str(pp['performance_review']['manager_id']):
                    pp['view'] = "Manager"
                else:
                    raise web.seeother('/performancereviews')
                return env.get_template('employees/performancereviews/edit.html').render(pp=pp)

        # Review submitted : send alert emails and set flag
        employee = corpdb.employees.find_one(ObjectId(pp['performance_review']['employee_id']))
        manager = corpdb.employees.find_one(ObjectId(pp['performance_review']['manager_id']))
        manager_email = manager['jira_uname']
        # If employee has just finished review:
        if str(pp['current_user']['_id']) == str(pp['performance_review']['employee_id']):
            # Send alert email to manager on first submit.
            if pp['performance_review']['status'] == "needs employee review":
                web.sendmail('cookbook@webpy.org', 'louisa.berger@10gen.com', ('New Manager Performance Review: '+
                    employee['first_name']+' '+employee['last_name']), 'You have a new performance review at http://corp.10gen.com/performancereviews.')
            # Set status flag to "needs manager review".
            pp['performance_review']['status'] = "needs manager review"
            # Set due date to 1 wk later for manager review
            pp['performance_review']['due_date'] = employee_model.add_days_to_date(pp['performance_review']['due_date'], 7)
        # If manager has just finished review:
        elif str(pp['current_user']['_id']) == str(pp['performance_review']['manager_id']):
            # On first submit, send alert email to HR and reminder email to manager to set up 1-1.
            if pp['performance_review']['status'] ==  "needs manager review":
                web.sendmail('cookbook@webpy.org', 'louisa.berger@10gen.com', ('Performance Review Completed: '+
                    employee['first_name']+' '+employee['last_name']), ('Performance review for '+employee['first_name']+' '+employee['last_name']+' has been completed: https://corp.10gen.com/performancereviews/'+pp['performance_review']['_id']))
                web.sendmail('cookbook@webpy.org', 'louisa.berger@10gen.com', 'Reminder: Schedule 1-1 for Performance Review',
                ('Reminder: Schedule a 1-1 meeting with '+employee['first_name']+' '+employee['last_name']+' to discuss their performace review.'))            
            # Set status flag to "needs meeting".
            pp['performance_review']['status'] = "needs meeting"
            # Set due date to 3 days later for setting up a meeting
            pp['performance_review']['due_date'] = employee_model.add_days_to_date(pp['performance_review']['due_date'], 7)
            # Check if manager wants to allow employee to view manager form early.
            if 'early_employee_view' in form.keys() and form['early_employee_view'] == "on":
                pp['performance_review']['early_employee_view'] = True
        
        corpdb.performancereviews.save(pp['performance_review'])
        raise web.seeother('/performancereviews/' + str(performance_review_id))


class NewPerformanceReview(CorpBase):
    @authenticated
    @require_admin
    def GET(self, pp, *args):
        print "GET NewPerformanceReview"
        pp['employees'] = corpdb.employees.find({"employee_status" : {"$ne" : "Former"}}).sort("first_name", pymongo.ASCENDING)
        # Default email message to be sent with new performance review alert
        pp['default_message'] = "You have a new performance review at http://corp.10gen.com/performancereviews. "
        return env.get_template('employees/performancereviews/new.html').render(pp=pp)

    @authenticated
    @require_admin
    def POST(self, pp):
        print "POST NewPerformanceReview"
        form = web.input()
        pp['error_message'] = ''
        # Set up employees to get reviews.
        employees = []
        if 'all_employees' in form.keys() and form['all_employees'] == 'on':
            employees = corpdb.employees.find( {"employee_status" : { "$ne" : "Former"}, "title" : {"$ne" : "CEO"}} )
        elif len(form['employee_id']) > 0:
            employees.append(corpdb.employees.find_one(ObjectId(form['employee_id']))) 
        else :
            raise web.seeother('/performancereviews/new')

        for employee in employees:
            date = datetime.now()
            name = employee['last_name']+employee['first_name']+str(date.year)+"_"+str(date.month)
            #Make sure there is not already a review for this employee this quarter.
            if corpdb.performancereviews.find( {'name': name} ).count() == 0:
                # TODO: better way to find manager...
                manager = employee_model.get_managers(employee)[0]
                due_date = employee_model.add_days_to_date(date, 7)

                performance_review = {'employee_id': employee['_id'], 'manager_id': manager['_id'], 'name' : name, 'date': date, 
                    'due_date' : due_date, 'status' : "needs employee review", 'early_employee_view' : False, 'employee_questions' : [], 'manager_questions': [] }
                
                # Add in review questions...
                employee_question_texts = employee_model.get_questions('Employee')
                employee_question_placeholders = employee_model.get_placeholders('Employee')
                manager_question_texts = employee_model.get_questions('Manager')
                manager_question_placeholders = employee_model.get_placeholders('Manager')
                for x in range(1, (len(employee_question_texts) + 1)):
                    performance_review['employee_questions'].append( {"name" : ("eq"+str(x)), "text": employee_question_texts[x-1], 
                        "placeholder" : employee_question_placeholders[x-1] })
                for x in range(1, (len(manager_question_texts) + 1)):
                    performance_review['manager_questions'].append( {"name" : ("mq"+str(x)), "text": manager_question_texts[x-1], 
                        "placeholder" : manager_question_placeholders[x-1] })
                
                try:
                    objectid = corpdb.performancereviews.insert(performance_review)
                except:
                    pp['error_message']+='\n'+(employee['first_name'] + ' ' + employee['last_name']+ ' could not be inserted.')
                if objectid:
                    # send email alert to employee and manager:
                    employee_email = employee['jira_uname']+"@10gen.com"
                    message = form['message'] + ' Employee self-review due by ' + str(due_date.month)+"/"+str(due_date.day)+'.'
                    web.sendmail('cookbook@webpy.org', 'louisa.berger@10gen.com', 'New Performance Review', message)
            else:
                pp['error_message']+='\n'+(employee['first_name'] + ' ' + employee['last_name']+ ' could not be inserted: a review for this employee already exists.')

        raise web.seeother('/performancereviews/')

class PerformanceReviewHRDashboard(CorpBase):
    @authenticated
    @require_admin
    def GET(self, pp, *args):
        print "GET PerformanceReviewHRDashboard"
        pp['performancereviews'] = corpdb.performancereviews.find().sort("name", pymongo.ASCENDING)
        pp['uncompleted_reviews'] = list(corpdb.performancereviews.find( { "status" : { "$ne" : "done"}, "due_date" : { "$gte" : employee_model.add_days_to_date(datetime.now(), -1)}} ).sort("name", pymongo.ASCENDING))
        pp['overdue_reviews'] = list(corpdb.performancereviews.find( {"status" :  { "$ne" : "done"}, "due_date" : { "$lt" : employee_model.add_days_to_date(datetime.now(), -1) } } ))
        return env.get_template('employees/performancereviews/hrdashboard.html').render(pp=pp)
    @authenticated
    @require_admin
    def POST(self, pp, *args):
        print "POST PerformanceReviewHRDashboard"
        form = web.input()
        if form['all_search']:
            raise web.seeother('/performancereviews/'+form['all_search'])

        raise web.seeother('/performancereviews')


class DeletePerformanceReview(CorpBase):
    @authenticated
    @require_admin
    def POST(self, pp, *args):
        print "POST DeletePerformanceReview"
        performance_review_id = args[0]
        corpdb.performancereviews.remove(ObjectId(performance_review_id))
        raise web.seeother('/performancereviews/')


class SendPerformanceReviewReminders(CorpBase):
    @authenticated
    @require_admin
    def GET(self, pp, *args):
        print "GET SendPerformanceReviewReminders"
        # Incomplete performance reviews.
        pp['performancereviews'] = corpdb.performancereviews.find( {"status" : { "$ne" : "done"}}).sort("name", pymongo.ASCENDING)
        return env.get_template('employees/performancereviews/sendreminders.html').render(pp=pp)
    @authenticated
    @require_admin
    def POST(self, pp,  *args):
        print "POST SendPerformanceReviewReminders"
        form = web.input()
        overdue_reviews = []
        email_address = ""
        subject = "Performance Review Reminder"
        if 'all_overdue' in form.keys() and form['all_overdue'] == "on":
            overdue_reviews = corpdb.performancereviews.find( {"status" :  { "$ne" : "done"}, "due_date" : { "$lt" : employee_model.add_days_to_date(datetime.now(), -1) } } )
        elif 'review_id' in form.keys():
            overdue_reviews.append(corpdb.performancereviews.find_one( {"_id" : ObjectId(form['review_id'])}))
        
        if 'message' in form.keys():
            message = form['message']

        print "overdue_reviews"
        
        for review in overdue_reviews:
            message = ""
            employee = corpdb.employees.find_one( ObjectId(review['employee_id']))
            manager = corpdb.employees.find_one(ObjectId(review['manager_id']))
            if review['status'] == "needs employee review":
                email_address = (employee['jira_uname']+"@10gen.com")
                if review['due_date'] < employee_model.add_days_to_date(datetime.now(), -1):
                    message+= ('Your employee self-review is overdue -- please fill it out at https://corp.10gen.com/performancereviews/'+str(review['_id']))
                else:
                    message+= ('Your employee self-review is due on ' + str(review['due_date'].month)+'/'+str(review['due_date'].day)+ ' -- please fill it out at https://corp.10gen.com/performancereviews/'+str(review['_id']))
            elif review['status'] == "needs manager review":
                email_address = (manager['jira_uname']+"@10gen.com")
                if review['due_date'] < employee_model.add_days_to_date(datetime.now(), -1):               
                    message+=('Your manager review for '+employee['first_name']+" "+employee['last_name']+" is overdue. Please fill it out at https://corp.10gen.com/performancereviews/"+str(review['_id']))
                else:
                    message+=('Your manager review for '+employee['first_name']+" "+employee['last_name']+" is due "+str(review['due_date'].month) +'/'+str(review['due_date'].day)+" Please fill it out at https://corp.10gen.com/performancereviews/"+str(review['_id']))
            elif review['status'] == "needs meeting":
                email_address = (manager['jira_uname'] + "@10gen.com")             
                message+=('Please schedule a meeting with '+employee['first_name']+" "+employee['last_name']+" to review their performance review.")
            elif review['status'] == "needs employee signature":
                email_address = (employee['jira_uname']+"@10gen.com")
                message+= ('Please sign off on your performance review at http://corp.10gen.com/performancereviews/'+str(review['_id']))
            else:
                raise web.seeother('performancereviews/hrdashboard')  
            #web.sendmail('cookbook@webpy.org', email_address, subject, message)
            web.sendmail('cookbook@webpy.org', 'louisa.berger@10gen.com', subject, message) 
        
        raise web.seeother('/performancereviews/hrdashboard')


                           
    


urls = (
        '/employees/(.*).vcf', ExportEmployeeVcard,
        '/employees/(.*)/edit', EditEmployee,
        '/employees/(.*)/rateskills', RateSkills,
        '/employees/(.*)/editemails', EditEmailAddress,
        '/employees/(.*)/editimage', EditEmployeeImage,
        '/employees/(.*)/newfield', NewEmployeeField,
        '/employees/(.*)/delete', DeleteEmployee,
        '/employees/(.*)/deleteimage', DeleteEmployeeImage,
        '/employees/new', NewEmployee,
        '/employees/(.*)', Employees,
        '/employees.csv', ExportEmployeesCSV,
        '/skillmatrix.csv', ExportEmployeesSkillsCSV,
        '/employees', EmployeesIndex,

        '/contacts.vcf', ExportAllEmployeesVcard,

        '/orgchart', OrgStructure,
        '/orgchart_list', OrgStructureList,

        '/teams/new', NewTeam,
        '/teams/(.*)/delete', DeleteTeam,
        '/teams/(.*)/edit', EditTeam,
        '/teams/(.*)', Teams,
        '/teams', Teams,

        '/skills/new', NewSkill,
        '/skills/(.*)/edit', EditSkill,
        '/skills/(.*)/delete', DeleteSkill,
		'/skills/(.*)', Skills,
		'/skills', Skills,

        '/skillgroups/new', NewSkillGroup,
        '/skillgroups/(.*)/edit', EditSkillGroup,
        '/skillgroups/(.*)/delete', DeleteSkillGroup,
		'/skillgroups/(.*)', SkillGroups,
		'/skillgroups', SkillGroups,

        '/projectgroups/new', NewProjectGroup,
        '/projectgroups/(.*)/remove_member/(.*)', RemoveProjectGroupMember,
        '/projectgroups/(.*)/new_member', NewProjectGroupMember,
        '/projectgroups/(.*)/edit', EditProjectGroup,
        '/projectgroups/(.*)/delete', DeleteProjectGroup,
        '/projectgroups/(.*)', ProjectGroups,
        '/projectgroups', ProjectGroups,

        '/profileimage/(.*)', ProfileImage,
        
        '/performancereviews/new', NewPerformanceReview,
        '/performancereviews/hrdashboard', PerformanceReviewHRDashboard,
        '/performancereviews/sendreminders', SendPerformanceReviewReminders,
        '/performancereviews/(.*)/edit', EditPerformanceReview,
        '/performancereviews/(.*)/delete', DeletePerformanceReview,
        '/performancereviews/(.*)', PerformanceReviews,
        '/performancereviews', PerformanceReviews,
)
