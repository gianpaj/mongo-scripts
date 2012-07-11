import os
import sys
import web
import pymongo
import gridfs
from bson.objectid import ObjectId
import hashlib
import hmac
#LOCAL
#from jinja2 import Environment, FileSystemLoader
import jinja2
import employee_model
import random
import md5
from util import _url_split, url_cmp

from corpbase import env, CorpBase, authenticated, the_crowd, eng_group, wwwdb, mongowwwdb, usagedb, pstatsdb, corpdb, ftsdb


#LOCAL
#def render_template(template_name, **context):
#    extensions = context.pop('extensions', [])
#    globals = context.pop('globals', {})
#
#    jinja_env = Environment(
#            loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates/employees')),
#            extensions=extensions,
#            )
#    jinja_env.globals.update(globals)
#
#    return jinja_env.get_template(template_name).render(context)
#


##LOCAL - this needs to be an authenticated db
#connection = pymongo.Connection("localhost", 27017)
#corpdb = connection.employee_info
#########


from functools import wraps

############### Roles and Control Wrappers #################
############################################################
def require_manager(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
             crowd_uname = web.cookies()['auth_user']
             if crowd_uname:
                 employee = corpdb.employees.find_one({"jira_uname" : crowd_uname })
                 role = employee['role']
             else:
                 role = 'employee'
        except:
             role = 'employee'

        print role
        if role == "manager":
            return f(self, *args, **kwargs)
        raise web.seeother('/employees')

    return wrapper

def require_admin(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
             crowd_uname = web.cookies()['auth_user']
             if crowd_uname:
                 employee = corpdb.employees.find_one({"jira_uname" : crowd_uname })
                 role = employee['role']
             else:
                 role = 'employee'
        except:
             role = 'employee'

        print role
        if role == "admin":
            return f(self, *args, **kwargs)
        raise web.seeother('/employees')

    return wrapper

def require_current_user(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        crowd_uname = args[0]['user']
        try:
             # Get employee crowd_uname from cookie
             crowd_uname = web.cookies()['auth_user']
             # Get employee from args to request
             employee = corpdb.employees.find_one({"jira_uname" : jira_uname})
        except:
             employee = False
        if employee:
             if employee['jira_uname'] == crowd_uname:
                 return f(self, *args, **kwargs)
        raise web.seeother('/employees')

    return wrapper

def require_manager_or_self(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
       try:
            crowd_uname = "spf13"#args[0]['user']
            print "crowd_uname: ", crowd_uname
            current_user = corpdb.employees.find_one({"jira_uname" : crowd_uname })
            requested_employee = corpdb.employees.find_one({"jira_uname": args[1] })
            if not requested_employee:
                 requested_employee = corpdb.employees.find_one({"_id": ObjectId(args[1]) })
       except:
            current_user = None
            requested_employee = None

       if requested_employee and current_user:
           print "requested employee: ", requested_employee['jira_uname']
           print "current_user: ", current_user
           requested_employees_managers = employee_model.get_managers(requested_employee)
           if current_user in requested_employees_managers or current_user["jira_uname"] == requested_employee["jira_uname"]:
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

def current_user_role(pp):
    crowd_name = pp['user']
    current_user = corpdb.employees.find_one({"jira_uname" : crowd_uname })
    try:
        role = current_user['role']
    except:
        role = ""
    return role

############################################################
# Employees
############################################################
class EmployeesIndex(CorpBase):
    @authenticated
    def GET(self, pp):
        print "GET EmployeesIndex"
        pp = {}

        # this isn't the most efficient way of getting a random document, but the collection is too small for it really to matter
        range_max = corpdb.employees.find().count()
        if range_max > 1:
            random_int = random.randint(1, range_max)
            print "random_int: ", random_int
            pp['random_employee'] = corpdb.employees.find().skip(random_int-1).next()
            pp['random_employee_primary_email'] = employee_model.primary_email(pp['random_employee'])
            # Set up hash for getting gravatar
            if pp['random_employee_primary_email']:
                pp['random_employee_hash'] = md5(pp['random_employee_primary_email'].strip())
            else:
                pp['random_employee_hash'] = ""

        #current_user = corpdb.employees.find_one({"jira_uname" : web.cookies()['auth_user']})
        pp['current_user_role'] = "manager"#current_user['role']

        pp['employees'] = corpdb.employees.find()

        return env.get_template('employees/employees/index.html').render(pp=pp)

    #SEARCH FORM SUBMITS TO HERE
    @authenticated
    def POST(self, pp):
        print "POST index"
        form = web.input()
        print form
        employee = corpdb.employees.find_one({"jira_uname": form['search']})
        print employee
        if employee:
            raise web.seeother('/employees/' + employee['jira_uname'])
        else:

            raise web.seeother('/employees')


class Employees(CorpBase):
    @authenticated
    #MEMBER SHOW PAGE
    def GET(self, pp, *args):
        print "GET employees"
        pp = {}
        pp['employee'] = corpdb.employees.find_one({"jira_uname": args[0]})

        if pp['employee'] is None:
            raise web.seeother('/employees')
        else:
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
            pp['manager_hierarchy'] = employee_model.get_manager_hierarchy(pp['employee'])
            print pp['manager_hierarchy']
            # Construct a list of skill names
            pp['skills'] = {}
            if 'skills' in pp['employee']:
                # TODO: use $in
                for skill_id in pp['employee']['skills']:
                     pp['skills'][str(skill_id)] = corpdb.skills.find_one(ObjectId(skill_id))

            # set up hash to get gravatar
            pp['employee']['email'] = employee_model.primary_email(pp['employee'])
            if pp['employee']['email']:
                 pp['gravatar_hash'] = md5(pp['employee']['email'].strip())
            else:
                 pp['gravatar_hash'] = ""

            pp['employee']['email_addresses'] = ""
            pp['employee']['email_addresses'] = ", ".join(pp['employee']['email_addresses'] )

            return env.get_template('employees/employees/show.html').render(pp=pp)


class EditEmployee(CorpBase):
    #DISPLAY EDIT PAGE
    @authenticated
    @require_manager_or_self
    def GET(self, pp, *args):
        print "GET EditEmployee"
        pp = {}
        jira_uname = args[0]
        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        if pp['employee'] is None:
            raise web.seeother('/employees')
        else:
            pp['offices'] = corpdb.employees.distinct("office")
            pp['statuses'] = corpdb.employees.distinct("employee_status")
            pp['team_members'] = corpdb.employees.find({"_id": {"$ne": pp['employee']['_id']}})
            pp['primary_email'] = employee_model.primary_email(pp['employee'])

            pp['extra_fields'] = []
            for n in pp['employee'].keys():
                if n not in employee_model.editable_keys() and n not in employee_model.no_show():
                    pp['extra_fields'].append(n)
            print "extra fields: ", pp['extra_fields']

            print pp['employee']['jira_uname'] 
            if pp['employee']['jira_uname'] == "emily.stolfo@10gen.com": #web.cookies()['auth_user']:

                pp['is_current_user'] = True
            else:
                pp['is_current_user'] = False

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
            tech_skill_group = corpdb.skill_groups.find_one({"name":"TECH"})
            industry_skill_group = corpdb.skill_groups.find_one({"name":"INDUSTRY"})
            general_skill_group = corpdb.skill_groups.find_one({"name":"GENERAL"})

            if tech_skill_group:
                pp['skill_groups']['TECH'] = []
                for skill in corpdb.skills.find({"groups": tech_skill_group["_id"]}):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['TECH'].append(skill)

            if industry_skill_group:
                pp['skill_groups']['INDUSTRY'] = []
                for skill in corpdb.skills.find({"groups": industry_skill_group["_id"]}):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['INDUSTRY'].append(skill)

		    if general_skill_group:
		        pp['skill_groups']['GENERAL'] = []
                for skill in corpdb.skills.find({"groups": general_skill_group["_id"]}):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['GENERAL'].append(skill)

            pp['teams'] = corpdb.teams.find()

            return env.get_template('employees/employees/edit.html').render(pp=pp)
            #return render_template('employees/edit.html', pp=pp)

    #EDIT FORM SUBMITS TO HERE
    @authenticated
    #@require_manager_or_self
    def POST(self, pp, *args): # maybe employee id?
        "POST EditEmployee"
        form = web.input(managing_ids=[], skills_TECH=[], skills_INDUSTRY=[], skills_GENERAL=[], team_ids=[])
        print form
        jira_uname = args[0]
        employee = corpdb.employees.find_one({"jira_uname": jira_uname})

        #a first name and last name must be entered
        if len(form['first_name']) > 0 and len(form['last_name']) > 0:

            for n in form.keys():
                if n.split("_")[0] == "skills":
                    for skill in form[n]:
                        if 'skills' not in employee:
                            employee['skills'] = {}
                        if skill not in employee['skills']:
                            employee["skills"][skill] = 1

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
                    employee['team_ids'] = map(lambda team_id: ObjectId(team_id), form['team_ids'])
                else:
                    employee[n] = form[n]

            #remove skills
            if employee['skills']:
                for skill in employee['skills'].keys():
                    if skill not in form['skills_TECH'] and skill not in form['skills_INDUSTRY'] and skill not in form['skills_GENERAL']:
                        del employee['skills'][skill]

            #remove managed_employees
            # TODO: use $pull instead
            managed_employees = corpdb.employees.find({"manager_ids": ObjectId(employee['_id'])})
            for managed_employee in managed_employees:
                if managed_employee['_id'] not in form['managing_ids']:
                    managed_employee['manager_ids'].remove(employee['_id'])
                    #corpdb.employees.save(managed_employee)

            # handle date
            employee['start_date'] = employee_model.generate_date(form['start_date'])
            employee['birthday'] = employee_model.generate_date(form['birthday'])
            corpdb.employees.save(employee)
            raise web.seeother('/employees/' + employee['jira_uname'])

        # first name or last name (or both) is blank.  Render edit page with error message.
        else:
            pp = {}
            pp['employee'] = employee
            pp['offices'] = corpdb.employees.distinct("office")
            pp['statuses'] = corpdb.employees.distinct("employee_status")
            pp['team_members'] = corpdb.employees.find({"_id": {"$ne": pp['employee']['_id']}})
            pp['primary_email'] = employee_model.primary_email(pp['employee'])


            print pp['employee']['jira_uname'] 
            if pp['employee']['jira_uname'] == "emily.stolfo@10gen.com": #web.cookies()['auth_user']:
               pp['is_current_user'] = True
            else:
                pp['is_current_user'] = False

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
            tech_skill_group = corpdb.skill_groups.find_one({"name":"TECH"})
            industry_skill_group = corpdb.skill_groups.find_one({"name":"INDUSTRY"})
            general_skill_group = corpdb.skill_groups.find_one({"name":"GENERAL"})
           
            if tech_skill_group:
                pp['skill_groups']['TECH'] = []
                for skill in corpdb.skills.find({"groups": tech_skill_group["_id"]}):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['TECH'].append(skill)
           
            if industry_skill_group:
                pp['skill_groups']['INDUSTRY'] = []
                for skill in corpdb.skills.find({"groups": industry_skill_group["_id"]}):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['INDUSTRY'].append(skill)

            if general_skill_group:
                pp['skill_groups']['GENERAL'] = []
                for skill in corpdb.skills.find({"groups": general_skill_group["_id"]}):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups']['GENERAL'].append(skill)

            pp['teams'] = corpdb.teams.find()
           
            pp['error_message'] = "You must have values for first and last name."
            return env.get_template('employees/employees/edit.html').render(pp=pp)
            #return render_template('employees/edit.html', pp=pp)


class RateSkills(CorpBase):
    @authenticated
    #@require_manager_or_self
    def GET(self, pp, *args):
        print "GET RateSkills"
        jira_uname = args[0]
        pp = {}
        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        if pp['employee'] is None or "skills" not in pp['employee'].keys():
            raise web.seeother('/employees')
        else:
            pp['primary_email'] = employee_model.primary_email(pp['employee'])
            pp['skills'] = {}
            # TODO: use $in - LEAVE as is because of objectid/string issues
            for skill_id in pp['employee']['skills']:
                pp['skills'][skill_id] = corpdb.skills.find_one(ObjectId(skill_id))['name']
            return env.get_template('employees/employees/rate_skills.html').render(pp=pp)
            #return render_template('employees/rate_skills.html', pp=pp)

    @authenticated
    #@require_manager_or_self
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
    #@require_manager
    def GET(self):
        print "GET NewEmployee"
        pp = {}
        pp['teams'] = corpdb.teams.find()
        return env.get_template('employees/employees/new.html').render(pp=pp)
        #return render_template('employees/new.html', pp=pp)

    @authenticated
    #@require_manager
    def POST(self, pp):
        print "POST NewEmployee"
        form = web.input()
        print form
        if len(form['first_name']) > 0 and len(form['last_name']) > 0 and len(form['email_address']) > 0 and len(form['jira_uname']) and len(form['team_id']):
            jira_uname = form['jira_uname'].lower()
            # make sure there are no other users with this email address
            employee = corpdb.employees.find_one({"jira_uname": jira_uname})
            print "employee found: ", employee
            if not employee:
                employee = {'first_name': form['first_name'],
                'last_name': form['last_name'],
                'email_addresses': [form['email_address']],
                'jira_uname': jira_uname,
                'team_ids':[ObjectId(form['team_id'])],
                'role': 'employee',
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
    #@require_manager_or_self
    def GET(self, pp, *args):
        print "GET EditEmailAddress"
        jira_uname = argos[0]
        pp = {}
        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        if pp['employee'] is not None:
            return env.get_template('employees/employees/edit_email_addresses.html').render(pp=pp)
            #return render_template('employees/edit_email_addresses.html', pp=pp)
        else:
            raise web.seeother('/employees/')

    @authenticated
    #@require_manager_or_self
    def POST(self, pp, *args):
        print "POST EditEmailAddress"
        form = web.input()
        print form
        jira_uname = args[0]
        employee = corpdb.employees.find_one({"jira_uname": jira_uname})
        if employee is not None:
            if "_method" in form.keys() and form["_method"] == "delete":
                print "deleting email address"
                print len(employee["email_addresses"])
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
    #@require_current_user
    def GET(self, jira_uname):
        print "GET NewEmployeeField"
        pp = {}
        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        if pp['employee'] is not None:
            return env.get_template('employees/employees/new_field.html').render(pp=pp)
            #return render_template('employees/new_field.html', pp=pp)
        else:
            raise web.seeother('/employees/')

    @authenticated
    #@require_current_user
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
    #@require_current_user
    def GET(self, pp, *args):
        print "GET EditEmployeeImage"
        pp = {}
        jira_uname = args[0]
        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        pp['employee_email_address'] = employee_model.primary_email(pp['employee'])
        pp['email_hash'] = employee_model.email_hash(pp['employee'])
        if pp['employee'] is not None:
            return env.get_template('employees/employees/edit_image.html').render(pp=pp)
            #return render_template('employees/edit_image.html', pp=pp)
        else:
            raise web.seeother('/employees/')

    @authenticated
    #@require_current_user
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
    #@require_current_user
    def POST(self, pp, *args):
        print "POST DeleteEmployeeImage"
        form = web.input()
        pp = {}
        
        gfs = gridfs.GridFS(corpdb)

        while gfs.exists({"filename" : jira_uname }):
            file = gfs.get_last_version(filename=jira_uname)
            gfs.delete(file._id)

        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        raise web.seeother('/employees/' + str(pp['employee']['jira_uname']) + "/edit")


class set_default_employee_email(CorpBase):
    @authenticated
    #@require_current_user
    def POST(self, pp, *args):
        print "POST set_default_employee_email"
        form = web.input()
        print form
        employee_id = args[0]
        employee = corpdb.employees.find_one({"_id": ObjectId(employee_id)})
        if employee is not None:
            if "email_addresses" in employee.keys():
                # is there a better way of bubbling up an element to position 0 of a list in python?
                employee['email_addresses'].remove(form['email_address'])
                employee['email_addresses'].insert(0, form['email_address'])
                corpdb.employees.save(employee)
            raise web.seeother('/employees/' + str(employee['_id']) + "/edit")
        else:
            raise web.seeother('/employees/')


class SetDefaultEmployeeEmail(CorpBase):
    @authenticated
    #@require_current_user
    def POST(self, pp, *args):
        print "POST SetDefaultEmployeeEmail"
        form = web.input()
        print form
        jira_uname = args[0]
        employee = corpdb.employees.find_one({"_id": ObjectId(jira_uname)})
        if employee is not None:
            if "email_addresses" in employee.keys():
                # is there a better way of bubbling up an element to position 0 of a list in python?
                employee['email_addresses'].remove(form['email_address'])
                employee['email_addresses'].insert(0, form['email_address'])
                corpdb.employees.save(employee)
            raise web.seeother('/employees/' + employee['jira_uname'] + "/edit")
        else:
            raise web.seeother('/employees/')


############################################################
# Org Structure
############################################################
class OrgStructure(CorpBase):
    @authenticated
    def GET(self):
        print "GET OrgStructure"
        pp = {}
        pp['org_structure'] = employee_model.org_structure()
        pp['teams'] = {}

        # Populate a dict of members for each team
        for team in corpdb.teams.find():
            pp['teams'][team['name']] = {}
            for employee in corpdb.employees.find({"team_ids": ObjectId(team['_id'])}):
                if employee['first_name'] and employee['last_name']:
                    pp['teams'][team['name']][str(employee['jira_uname'])] = str(employee['first_name'] + " " + employee['last_name'])

        pp['org_chart'] = employee_model.org_structure_list()

        return env.get_template('employees/employees/org_chart_jquery.html').render(pp=pp)
        #return render_template('employees/org_chart_jquery.html', pp=pp)


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
    def GET(self, team_id=""):
        print "GET Teams"
        pp = {}
        print team_id
        if team_id:
            pp['team'] = corpdb.teams.find_one(ObjectId(team_id))

            if pp['team']:
	            pp['team_members'] = corpdb.employees.find({"team_ids": pp['team']['_id']})
	            pp['managed_teams'] = corpdb.teams.find({"managing_team_ids": pp['team']['_id']})
	            if "managing_team_ids" in pp['team']:
	                pp['managing_teams'] = corpdb.teams.find({"_id" : { "$in" : pp['team']['managing_team_ids']}})

	            return env.get_template('employees/teams/show.html').render(pp=pp)
	            #return render_template('teams/show.html', pp=pp)
            else:
	            print "team not found"
	            raise web.seeother('/teams')
        else:
            pp['teams'] = corpdb.teams.find()
            return env.get_template('employees/teams/index.html').render(pp=pp)
            #return render_template('teams/index.html', pp=pp)

    @authenticated
    def POST(self, pp):
        print "POST Teams index (search)"
        form = web.input()
        print form
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
    #@require_manager
    def GET(self, pp, *args):
        print "GET EditTeam"
        pp = {}
        team_id = args[0]
        pp['team'] = corpdb.teams.find_one(ObjectId(team_id))

        if pp['team'] is None:
            print "team is none"
            raise web.seeother('/teams')
        else:
            pp['teams'] = corpdb.teams.find({"_id": {"$ne": pp['team']['_id']}})
            return env.get_template('employees/teams/edit.html').render(pp=pp)
            #return render_template('teams/edit.html', pp=pp)

    @authenticated
    #@require_manager
    def POST(self, pp, *args):
        print "POST EditTeam"
        form = web.input(managing_team_ids=[])
        print form
        team_id = args[0]
        team = corpdb.teams.find_one(ObjectId(team_id))

        # Name cannot be blank
        if len(form['name']) > 0:
            #if corpdb.teams.find({"_id": ObjectId(team_id)})
            team['name'] = form['name'].capitalize() 
            team['managing_team_ids'] = map(lambda id: ObjectId(id), form['managing_team_ids'])
            corpdb.teams.save(team)
            raise web.seeother('/teams/' + str(team['_id']))
        else:
            raise web.seeother('/teams')


class NewTeam(CorpBase):
    @authenticated
    #@require_manager
    def GET(self):
        print "GET NewTeam"
        return env.get_template('employees/teams/new.html').render(pp=pp)
        #return render_template('teams/new.html')

    @authenticated
    #@require_manager
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
    #@require_manager
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
# Skill Groups
############################################################
class SkillGroups(CorpBase):
    @authenticated
   # @require_manager
    def GET(self, pp, *args):
        print "GET SkillGroups"
        pp = {}
        skill_group_id = args[0]
        if skill_group_id:
            pp['skill_group'] = corpdb.skill_groups.find_one(ObjectId(skill_group_id))

            if pp['skill_group']:
	            pp['skills'] = []
                # TODO: use $in instead
	            for skill in corpdb.skills.find({"groups": pp['skill_group']['_id']}):
	                pp['skills'].append(skill)
	            return env.get_template('employees/skillgroups/show.html').render(pp=pp)
	            #return render_template('skillgroups/show.html', pp=pp)

            else:
                print "skill not found"
                raise web.seeother('/skillgroups')
        else:
            pp['skill_groups'] = corpdb.skill_groups.find()
            return env.get_template('employees/skillgroups/index.html').render(pp=pp)
            #return render_template('skillgroups/index.html', pp=pp)

    @authenticated
    #@require_manager
    def POST(self, pp):
        print "POST SkillGroups index (search)"
        form = web.input()
        print form
        pp = {}
        pp['skill_group'] = corpdb.skill_groups.find_one(ObjectId(form['search']))
        print pp['skill_group']
        if pp['skill_group'] is None:
            raise web.seeother('/skillgroups')
        else:
            print "skillgroup found"
            raise web.seeother('/skillgroups/' + form['search'])


############################################################
# Skills
############################################################
class Skills(CorpBase):
    @authenticated
    def GET(self, pp, *args):
        print "GET Skills"
        pp = {}
        
        try:
            skill_id = args[0]
        except:
            skill_id = ""
        #current_user = corpdb.employees.find_one({"jira_uname" : web.cookies()['auth_user']})
        pp['current_user_role'] = "manager"#current_user['role']

        if skill_id:
            pp['skill'] = corpdb.skills.find_one(ObjectId(skill_id))

            if pp['skill']:
                # Change the ObjectId to a string to be used in the employee skills embedded doc
                pp['skill']['_id'] = str(pp['skill']['_id'])
                pp['skill_groups'] = []
                pp['employees'] = []
                pp['skill_groups'] = corpdb.skill_groups.find({"_id" : { "$in" : pp['skill']['groups']}})
                pp['employees'] = corpdb.employees.find({"skills."+ str(pp['skill']['_id']): {"$exists":True} })
                # Sort employees by their skill level
                pp['employees'] = sorted(pp['employees'], key=lambda employee: -employee['skills'][str(pp['skill']['_id'])])
                return env.get_template('employees/skills/show.html').render(pp=pp)
                #return render_template('skills/show.html', pp=pp)

            else:
                print "skill not found"
                raise web.seeother('/skills')
        else:
            pp['skills'] = corpdb.skills.find()
            return env.get_template('employees/skills/index.html').render(pp=pp)
            #return render_template('skills/index.html', pp=pp)

    @authenticated
    def POST(self, pp):
        print "POST Skills index (search)"
        form = web.input()
        print form
        pp = {}
        pp['skill'] = corpdb.skills.find_one(ObjectId(form['search']))
        print pp['skill']
        if pp['skill'] is None:
            raise web.seeother('/skills')
        else:
            print "skill found"
            raise web.seeother('/skills/' + form['search'])


class EditSkill(CorpBase):
     #@require_manager
     def GET(self, skill_id):
         print "GET EditSkill"
         pp = {}
         pp['skill'] = corpdb.skills.find_one(ObjectId(skill_id))
         if pp['skill']:
             pp['skill_groups'] = corpdb.skill_groups.find()
             return env.get_template('employees/skills/edit.html').render(pp=pp)
             #return render_template("skills/edit.html", pp=pp)
         else:
             raise web.seeother('/skills')

     #@require_manager
     def POST(self, skill_id):
         print "POST EditSkill"
         form = web.input(skill_groups=[])
         print form
         pp = {}
         pp['skill'] = corpdb.skills.find_one(ObjectId(skill_id))
         #Name cannot be blank in order for this skill to be saved
         if len(form['name']) > 0:
             # Only save the name if it's unique
             if corpdb.skills.find({"name": form['name'].upper() }).count() == 0:
                 pp['skill']['name'] = form['name'].upper()
             # Save the skill group ids
             pp['skill']['groups'] = map(lambda skill_group_id: ObjectId(skill_group_id), form['skill_groups'])
             corpdb.skills.save(pp['skill'])
             raise web.seeother('/skills/' + str(pp['skill']['_id']))
         raise web.seeother('/skills')


class NewSkill(CorpBase):
    #@require_manager
    def GET(self):
        print "GET NewSkill"
        return env.get_template('employees/skills/new.html').render(pp=pp)
        #return render_template('skills/new.html')

    #@require_manager
    def POST(self, pp):
        print "POST NewSkill"
        form = web.input()
        if len(form['name']) > 0:
            # make sure there are no other skills with this name
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
    #@require_manager
    def POST(self, skill_id):
        print "POST DeleteSkill"
        corpdb.employees.update({"skills."+ skill_id: {"$exists":True} }, {"$unset": {"skills."+ skill_id: 1}}, upsert=False, multi=True)
        corpdb.skills.remove(ObjectId(skill_id))
        raise web.seeother('/skills')


############################################################
# Skill Groups
############################################################
class SkillGroups(CorpBase):
   # @require_manager
    def GET(self, skill_group_id=""):
        print "GET SkillGroups"
        pp = {}
        if skill_group_id:
            pp['skill_group'] = corpdb.skill_groups.find_one(ObjectId(skill_group_id))

            if pp['skill_group']:
	            pp['skills'] = []
                # TODO: use $in instead
	            for skill in corpdb.skills.find({"groups": pp['skill_group']['_id']}):
	                pp['skills'].append(skill)
	            return env.get_template('employees/skillgroups/show.html').render(pp=pp)
	            #return render_template('skillgroups/show.html', pp=pp)

            else:
                print "skill not found"
                raise web.seeother('/skillgroups')
        else:
            pp['skill_groups'] = corpdb.skill_groups.find()
            return env.get_template('employees/skillgroups/index.html').render(pp=pp)
            #return render_template('skillgroups/index.html', pp=pp)

    #@require_manager
    def POST(self, pp):
        print "POST SkillGroups index (search)"
        form = web.input()
        print form
        pp = {}
        pp['skill_group'] = corpdb.skill_groups.find_one(ObjectId(form['search']))
        print pp['skill_group']
        if pp['skill_group'] is None:
            raise web.seeother('/skillgroups')
        else:
            print "skillgroup found"
            raise web.seeother('/skillgroups/' + form['search'])


class EditSkillGroup(CorpBase):
     #@require_manager
     def GET(self, skill_group_id):
         print "GET EditSkillGroup"
         pp = {}
         pp['skill_group'] = corpdb.skill_groups.find_one(ObjectId(skill_group_id))
         if pp['skill_group']:
             return env.get_template('employees/skillgroups/edit.html').render(pp=pp)
             #return render_template("skillgroups/edit.html", pp=pp)
         else:
             raise web.seeother('/skillgroups')

     #@require_manager
     def POST(self, skill_group_id):
         print "POST EditSkillGroup"
         form = web.input()
         print form
         pp = {}
         pp['skill_group'] = corpdb.skill_groups.find_one(ObjectId(skill_group_id))

         #Name cannot be blank
         if len(form['name']) > 0:
             if corpdb.skill_groups.find({"name": form['name']}).count() == 0:
                 pp['skill_group']['name'] = form['name']
                 corpdb.skill_groups.save(pp['skill_group'])
                 raise web.seeother('/skillgroups/' + str(pp['skill_group']['_id']))
         raise web.seeother('/skillgroups')


############################################################
# Project Groups
############################################################
class ProjectGroups(CorpBase):
   # TODO @require who?
    def GET(self, project_group_id=""):
        print "GET ProjectGroups"
        pp = {}
        if project_group_id:
            pp['project_group'] = corpdb.project_groups.find_one(ObjectId(project_group_id))

            if pp['project_group']:
                pp['employees'] = []
                for member in pp['project_group']['members']:
                    employee = corpdb.employees.find_one(ObjectId(member['employee_id']))
                    employee['project_role'] = member['role']
                    pp['employees'].append(employee)
                return env.get_template('employees/project_groups/show.html').render(pp=pp)
                #return render_template('project_groups/show.html', pp=pp)

            else:
                print "project group not found"
                raise web.seeother('/project_groups')
        else:
            pp['project_groups'] = corpdb.project_groups.find()
            pp['current_user_role'] = "manager"
            return env.get_template('employees/project_groups/index.html').render(pp=pp)
            #return render_template('project_groups/index.html', pp=pp)

    # TODO @require who?
    def POST(self, pp):
        print "POST ProjectGroups index (search)"
        form = web.input()
        print form
        pp = {}
        pp['project_group'] = corpdb.project_groups.find_one(ObjectId(form['search']))
        if pp['project_group'] is None:
            raise web.seeother('/project_groups')
        else:
            print "project_group found"
            raise web.seeother('/project_groups/' + form['search'])

class NewProjectGroup(CorpBase):
    # TODO @require who?
    def GET(self):
        print "GET NewProjectGroup"
        pp = {}
        pp['employees'] = corpdb.employees.find()
        return env.get_template('employees/project_groups/new.html').render(pp=pp)
        #return render_template('project_groups/new.html', pp=pp)

    # TODO @require who?
    def POST(self):
        print "POST NewProjectGroup"
        form = web.input()
        if len(form['name']) > 0 and len(form['lead']) > 0:
            project_group = {'name': form['name'], 'members' : [{'employee_id': ObjectId(form['lead']), 'role': 'LEAD'}] }
            try:
                objectid = corpdb.project_groups.insert(project_group)
            except:
                print "project_group not inserted"
            if objectid:
                raise web.seeother('/project_groups/' + str(objectid) + "/edit")
            else:
                raise web.seeother('/project_groups')
        raise web.seeother('/project_groups')


class EditProjectGroup(CorpBase):
     #@require_manager
     def GET(self, project_group_id):
         print "GET EditProjectGroup"
         pp = {}
         pp['project_group'] = corpdb.project_groups.find_one(ObjectId(project_group_id))
         pp['roles'] = ['PRODUCT MANAGER','PROJECT MANAGER', 'DOCUMENTER','DEVELOPER','STAKEHOLDER']
         if pp['project_group']:
             pp['employees'] = []
             for member in pp['project_group']['members']:
                 employee = corpdb.employees.find_one(ObjectId(member['employee_id']))
                 employee['project_role'] = member['role']
                 pp['employees'].append(employee) 
             return env.get_template('employees/project_groups/edit.html').render(pp=pp)            
             #return render_template("project_groups/edit.html", pp=pp)
         else:
             raise web.seeother('/project_groups')

     #@require_manager
     def POST(self, project_group_id):
         print "POST EditProjectGroup"
         form = web.input()
         print form
         pp = {}
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
             raise web.seeother('/project_groups/' + str(pp['project_group']['_id']))
         raise web.seeother('/project_groups')

class NewProjectGroupMember(CorpBase):
    # TODO @require who?
    def GET(self, project_group_id):
        print "GET NewProjectGroupMember"
        pp = {}
        pp['project_group_id'] = project_group_id
        project_group = corpdb.project_groups.find_one(ObjectId(project_group_id))
        # get ids of all members of the project group
        member_ids = map(lambda member: member['employee_id'], project_group['members'])
        # only get the employees who are not already in the project group for dropdown
        pp['employees'] = corpdb.employees.find({"_id": {"$nin": member_ids}})
        pp['roles'] = ['PRODUCT MANAGER','PROJECT MANAGER', 'DOCUMENTER','DEVELOPER','STAKEHOLDER']
        return env.get_template('employees/project_groups/new_member.html').render(pp=pp)
        #return render_template('project_groups/new_member.html', pp=pp)

    # TODO @require who?
    def POST(self, project_group_id):
        print "POST NewProjectGroupMember"
        form = web.input()
        if len(form['member']) > 0 and len(form['role']) > 0:
            project_group = corpdb.project_groups.find_one(ObjectId(project_group_id))
            if project_group: # TODO: can't add a member who is already in the list
                project_group['members'].append({'employee_id':ObjectId(form['member']), 'role': form['role']})
                corpdb.project_groups.save(project_group)
        raise web.seeother('/project_groups/' + project_group_id + '/edit')


class RemoveProjectGroupMember(CorpBase):
    # TODO @require who?
    def POST(self, project_group_id):
        print "POST RemoveProjectGroupMember"
        corpdb.project_groups.remove(ObjectId(project_group_id))
        raise web.seeother('/project_groups')


class DeleteProjectGroup(CorpBase):
    # TODO @require who?
    def POST(self, project_group_id):
        print "POST DeleteProjectGroup"
        corpdb.project_groups.remove(ObjectId(project_group_id))
        raise web.seeother('/project_groups')


urls = (
        '/employees/(.*)/edit', EditEmployee,
        '/employees/(.*)/rateskills', RateSkills,
        '/employees/(.*)/editemails', EditEmailAddress,
        '/employees/(.*)/editimage', EditEmployeeImage,
        '/employees/(.*)/newfield', NewEmployeeField,
        '/employees/(.*)/deleteimage', DeleteEmployeeImage,
        '/employees/(.*)/setdefaultemail', SetDefaultEmployeeEmail,
        '/employees/new', NewEmployee,
        '/employees/(.*)', Employees,
        '/employees', EmployeesIndex,

        '/orgchart', OrgStructure,

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

        '/skillgroups/(.*)/edit', EditSkillGroup,
		'/skillgroups/(.*)', SkillGroups,
		'/skillgroups', SkillGroups,

        '/project_groups/new', NewProjectGroup,
        '/project_groups/(.*)/remove_member/(.*)', RemoveProjectGroupMember,
        '/project_groups/(.*)/new_member', NewProjectGroupMember,
        '/project_groups/(.*)/edit', EditProjectGroup,
        '/project_groups/(.*)/delete', DeleteProjectGroup,
        '/project_groups/(.*)', ProjectGroups,
        '/project_groups', ProjectGroups,

        '/profileimage/(.*)', ProfileImage,
)
