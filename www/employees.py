import os
import sys
import web
import pymongo
import gridfs
from bson.objectid import ObjectId
import hashlib
#LOCAL
from jinja2 import Environment, FileSystemLoader
#import jinja2
import employee_model
import random
import md5
from util import _url_split, url_cmp

# some path stuff
here = os.path.dirname(os.path.abspath(__file__))
if here not in sys.path:
    sys.path.append(here)

sys.path.append( here.rpartition( "/" )[0] + "/lib" )
sys.path.append( here.rpartition( "/" )[0] + "/support" )

#from corpbase import env, CorpBase, authenticated, the_crowd, eng_group, wwwdb, mongowwwdb, usagedb, pstatsdb, corpdb, ftsdb

# setup web env
#env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(here, "templates")))


#class CorpNormal(CorpBase):
#    @authenticated
#    def POST(self, pageParams, p=''):
#        return self.GET(p)
#
#    @authenticated
#    def GET(self, pageParams, p=''):
#        if p == "logout":
#            return web.redirect( "/" )
#
#        if p in dir(self):
#            getattr(self,p)(pageParams)
#
#        #print( pageParams )
#
#        #fix path
#        if p == "":
#            p = "index.html"
#
#        if not p.endswith( ".html" ):
#            p = p + ".html"
#
#        pageParams["path"] = '/employees/' + p
#
#        t = env.get_template( p )
#        return t.render(**pageParams)
#

#LOCAL
def render_template(template_name, **context):
    extensions = context.pop('extensions', [])
    globals = context.pop('globals', {})

    jinja_env = Environment(
            loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates/employees')),
            extensions=extensions,
            )
    jinja_env.globals.update(globals)

    return jinja_env.get_template(template_name).render(context)


# share some globals through web.config
#web.config.env = env


#LOCAL
connection = pymongo.Connection("localhost", 27017)
corpdb = connection.employee_info
########

urls = (
        '/employees/(.*)/edit', 'EditEmployee',
        '/employees/(.*)/rateskills', 'RateSkills',
        '/employees/(.*)/editemails', 'EditEmailAddress',
        '/employees/(.*)/editimage', 'EditEmployeeImage',
        '/employees/(.*)/deleteimage', 'DeleteEmployeeImage',
        '/employees/(.*)/setdefaultemail', 'SetDefaultEmployeeEmail',
        '/employees/new', 'NewEmployee',
        '/employees/(.*)', 'Employees',
        '/employees', 'EmployeesIndex',

        '/orgchart', 'OrgStructure',

        '/teams/new', 'NewTeam',
        '/teams/(.*)/delete', 'DeleteTeam',
        '/teams/(.*)/edit', 'EditTeam',
        '/teams/(.*)', 'Teams',
        '/teams', 'Teams',

        '/skills/new', 'NewSkill',
        '/skills/(.*)/edit', 'EditSkill',
        '/skills/(.*)/delete', 'DeleteSkill',
		'/skills/(.*)', 'Skills',
		'/skills', 'Skills',

        '/skillgroups/(.*)/edit', 'EditSkillGroup',
		'/skillgroups/(.*)', 'SkillGroups',
		'/skillgroups', 'SkillGroups',
		
        '/profileimage/(.*)', 'ProfileImage',
)

from functools import wraps

def require_manager(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
             crowd_uname = web.cookies()['auth_user'].split("@")[0]
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

def require_current_user(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        jira_uname = args[0]
        try:
             # Get employee crowd_uname from cookie
             crowd_uname = "emily.stolfo@10gen.com".split("@")[0]#web.cookies()['auth_user'].split("@")[0]
             # Get employee from args to request
             employee = corpdb.employees.find_one({"jira_uname" : jira_uname})
        except:
             employee = False
        print employee
        if employee:
             if employee['jira_uname'] == crowd_uname:
                 return f(self, *args, **kwargs)
        raise web.seeother('/employees')

    return wrapper

def require_manager_or_self(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
             crowd_uname = "emily.stolfo@10gen.com".split("@")[0]#web.cookies()['auth_user'].split("@")[0]
             print "crowd_uname: ", crowd_uname
             current_user = corpdb.employees.find_one({"jira_uname" : crowd_uname })
             requested_employee = corpdb.employees.find_one({"jira_uname": args[0] })
             if not requested_employee:
                  requested_employee = corpdb.employees.find_one({"_id": ObjectId(args[0]) })
        except:
             current_user = None
             requested_employee = None
        print "requested employee: ", requested_employee['jira_uname']
        print "current_user: ", current_user
        if requested_employee and current_user:
             requested_employees_managers = employee_model.get_managers(requested_employee)
             print "requested_employees_managers: ", requested_employees_managers
             print current_user in requested_employees_managers
             if current_user in requested_employees_managers or current_user["jira_uname"].split("@")[0] == requested_employee["jira_uname"]:
                 return f(self, *args, **kwargs)
        raise web.seeother('/employees')
    return wrapper

def md5(s):
    m = hashlib.md5()
    m.update(s)
    return m.hexdigest()


class EmployeesIndex:
    def GET(self):
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
        pp['current_user_role'] = "employee"#current_user['role']

        pp['employees'] = corpdb.employees.find()

        return render_template('employees/index.html', pp=pp)

    #SEARCH FORM SUBMITS TO HERE
    def POST(self):
        print "POST index"
        form = web.input()
        print form
        employee = corpdb.employees.find_one({"jira_uname": form['search']})
        print employee
        if employee:
            raise web.seeother('/employees/' + employee['jira_uname'])
        else:

            raise web.seeother('/employees')


class Employees:
    #MEMBER SHOW PAGE
    def GET(self, param):
        print "GET employees"
        pp = {}
        pp['employee'] = corpdb.employees.find_one({"jira_uname": param})
        if pp['employee'] is None:
            raise web.seeother('/employees')
        else:
            pp['display_keys'] = employee_model.display_keys()
            pp['no_show'] = employee_model.no_show()
            # Construct a list of links to team pages
            pp['teams'] = []
            if 'team_ids' in pp['employee']:
                teams = corpdb.teams.find({"_id" : {"$in": pp['employee']['team_ids'] }})
                for team in teams:
	                link = "<a href='/teams/{0}'>{1}</a>".format(team["_id"], team['name'])
	                pp['teams'].append(link)

            pp['managers'] = employee_model.get_managers(pp['employee'])

            # Construct a list of skill names
            pp['skills'] = []
            if 'skills' in pp['employee']:
                # TODO: use $in
                for skill_id in pp['employee']['skills']:
                     print skill_id
                     pp['skills'].append(corpdb.skills.find_one(ObjectId(skill_id))['name'])

            # set up hash to get gravatar
            pp['employee']['email'] = employee_model.primary_email(pp['employee'])
            if pp['employee']['email']:
                 pp['gravatar_hash'] = md5(pp['employee']['email'].strip())
            else:
                 pp['gravatar_hash'] = ""

            pp['employee']['email_addresses'] = ""
            pp['employee']['email_addresses'] = ", ".join(pp['employee']['email_addresses'] )

            return render_template('employees/show.html', pp=pp)


class EditEmployee:
    #DISPLAY EDIT PAGE
    @require_manager_or_self
    def GET(self, jira_uname):
        print "GET EditEmployee"
        pp = {}

        pp['offices'] = corpdb.employees.distinct("office")
        pp['statuses'] = corpdb.employees.distinct("employee_status")
        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        if pp['employee'] is None:
            raise web.seeother('/employees')
        else:
            pp['team_members'] = corpdb.employees.find({"_id": {"$ne": pp['employee']['_id']}})
            pp['primary_email'] = employee_model.primary_email(pp['employee'])


            print pp['employee']['jira_uname'] 
            if pp['employee']['jira_uname'] == "emily.stolfo@10gen.com".split("@")[0]: #web.cookies()['auth_user'].split("@")[0]:

                pp['is_current_user'] = True
            else:
                pp['is_current_user'] = False

            # set up hash to get gravatar
            pp['primary_email'] = employee_model.primary_email(pp['employee'])
            pp['gravatar_hash'] = md5(pp['primary_email'].strip())

            # format the dates (i.e. get rid of the time)
            try:
                pp['birthday'] = pp['employee']["birthday"].strftime("%d-%m-%Y")
            except:
                pp['birthday'] = ""

            try:
                pp['anniversary'] = pp['employee']["anniversary"].strftime("%d-%m-%Y")
            except:
                pp['anniversary'] = ""

            #set up dict for skills and their groups
            pp['skill_groups'] = {}
            for skill_group in corpdb.skill_groups.find():
                pp['skill_groups'][skill_group['name']] = []
                # need to do this because the embedded skills doc has keys on the string ObjectId
                for skill in corpdb.skills.find({"groups": skill_group["_id"]}):
                    skill['id'] = str(skill['_id'])
                    pp['skill_groups'][skill_group['name']].append(skill)


            pp['teams'] = corpdb.teams.find()

            return render_template('employees/edit.html', pp=pp)

    #EDIT FORM SUBMITS TO HERE
    @require_manager_or_self
    def POST(self, jira_uname): # maybe employee id?
        "POST EditEmployee"
        form = web.input(managing_ids=[], skills=[], team_ids=[])
        print form
        employee = corpdb.employees.find_one({"jira_uname": jira_uname})

        #a first name and last name must be entered
        if len(form['first_name']) > 0 and len(form['last_name']) > 0:

            for n in form.keys():
                if n == "skills":
                    for skill in form["skills"]:
                        if skill not in employee['skills'].keys():
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
                    if skill not in form['skills']:
                        del employee['skills'][skill]

            #remove managed_employees
            # TODO: use $pull instead
            managed_employees = corpdb.employees.find({"manager_ids": ObjectId(employee['_id'])})
            for managed_employee in managed_employees:
                if managed_employee['_id'] not in form['managing_ids']:
                    managed_employee['manager_ids'].remove(employee['_id'])
                    #corpdb.employees.save(managed_employee)

            # handle date
            employee['anniversary'] = employee_model.generate_date(form['anniversary'])
            employee['birthday'] = employee_model.generate_date(form['birthday'])
            corpdb.employees.save(employee)
            raise web.seeother('/employees/' + employee_model.primary_email(employee))

        # first name or last name (or both) is blank.  Render edit page with error message.
        else:
             pp = {}

             pp['offices'] = corpdb.employees.distinct("office")
             pp['statuses'] = corpdb.employees.distinct("employee_status")
             pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
             if pp['employee'] is None:
                 raise web.seeother('/employees')
             else:
                 pp['team_members'] = corpdb.employees.find({"_id": {"$ne": pp['employee']['_id']}})
                 pp['primary_email'] = employee_model.primary_email(pp['employee'])


                 print pp['employee']['jira_uname'] 
                 if pp['employee']['jira_uname'] == "emily.stolfo@10gen.com".split("@")[0]: #web.cookies()['auth_user'].split("@")[0]:

                     pp['is_current_user'] = True
                 else:
                     pp['is_current_user'] = False

                 # set up hash to get gravatar
                 pp['primary_email'] = employee_model.primary_email(pp['employee'])
                 pp['gravatar_hash'] = md5(pp['primary_email'].strip())

                 # format the dates (i.e. get rid of the time)
                 try:
                     pp['birthday'] = pp['employee']["birthday"].strftime("%d-%m-%Y")
                 except:
                     pp['birthday'] = ""

                 try:
                     pp['anniversary'] = pp['employee']["anniversary"].strftime("%d-%m-%Y")
                 except:
                     pp['anniversary'] = ""

                 #set up dict for skills and their groups
                 pp['skill_groups'] = {}
                 for skill_group in corpdb.skill_groups.find():
                     pp['skill_groups'][skill_group['name']] = []
                     # need to do this because the embedded skills doc has keys on the string ObjectId
                     for skill in corpdb.skills.find({"groups": skill_group["_id"]}):
                         skill['id'] = str(skill['_id'])
                         pp['skill_groups'][skill_group['name']].append(skill)


                 pp['teams'] = corpdb.teams.find()

                 return render_template('employees/edit.html', pp=pp)


class RateSkills:
    @require_manager_or_self
    def GET(self, jira_uname):
        print "GET RateSkills"
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
            return render_template('employees/rate_skills.html', pp=pp)

    @require_manager_or_self
    def POST(self, jira_uname):
        print "POST RateSkills"
        form = web.input()
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


class NewEmployee:
    @require_manager
    def GET(self):
        print "GET NewEmployee"
        return render_template('employees/new_employee.html')

    @require_manager
    def POST(self):
        print "POST NewEmployee"
        form = web.input()
        if len(form['first_name']) > 0 and len(form['last_name']) > 0 and len(form['email_address']) > 0:
            # make sure there are no other users with this email address
            employee = corpdb.employees.find_one({"email_addresses": form['email_address']})
            if not employee:
                employee = {'first_name': form['first_name'],
                'last_name': form['last_name'],
                'email_addresses': [form['email_address']],
                'role': 'employee'
                }
                objectid = corpdb.employees.insert(employee)
                raise web.seeother('/employees/' + str(objectid) + "/edit")
            else:
                raise web.seeother('/employees/' + employee_model.primary_email(employee))
        else:
            raise web.seeother('/employees')


class EditEmailAddress:
    @require_manager_or_self
    def GET(self, jira_uname):
        print "GET EditEmailAddress"
        pp = {}
        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        if pp['employee'] is not None:
            return render_template('employees/edit_email_addresses.html', pp=pp)
        else:
            raise web.seeother('/employees/')

    @require_manager_or_self
    def POST(self, jira_uname):
        print "POST EditEmailAddress"
        form = web.input()
        print form
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


class EditEmployeeImage:
    #@require_current_user
    def GET(self, jira_uname):
        print "GET EditEmployeeImage"
        pp = {}
        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        pp['employee_email_address'] = employee_model.primary_email(pp['employee'])
        pp['email_hash'] = employee_model.email_hash(pp['employee'])
        if pp['employee'] is not None:
            return render_template('employees/edit_image.html', pp=pp)
        else:
            raise web.seeother('/employees/')

    @require_current_user
    def POST(self, jira_uname):
        print "POST EditEmployeeImage"
        image = web.input(image_file={})['image_file']
        if image.value != "":
            gfs = gridfs.GridFS(corpdb)
            gfs.put(image.value, filename=jira_uname)

        employee = corpdb.employees.find_one({"jira_uname": jira_uname})
        if employee:
            raise web.seeother('/employees/' + employee['jira_uname'] + "/edit")
        else:
            raise web.seeother('/employees/')


class DeleteEmployeeImage:
    @require_current_user
    def POST(self, jira_uname):
        print "POST DeleteEmployeeImage"
        form = web.input()
        pp = {}
        gfs = gridfs.GridFS(corpdb)

        while gfs.exists({"filename" : jira_uname }):
            file = gfs.get_last_version(filename=jira_uname)
            gfs.delete(file._id)

        pp['employee'] = corpdb.employees.find_one({"jira_uname": jira_uname})
        raise web.seeother('/employees/' + str(pp['employee']['jira_uname']) + "/edit")


class SetDefaultEmployeeEmail:
    @require_current_user
    def POST(self, jira_uname):
        print "POST SetDefaultEmployeeEmail"
        form = web.input()
        print form
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


class OrgStructure:
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
        print pp['org_structure']

        return render_template('employees/org_chart.html', pp=pp)


class ProfileImage:
    def GET(self, jira_uname):
        print "GET ProfileImage"
        gfs = gridfs.GridFS(corpdb)
        try:
            f = gfs.get_last_version(filename=jira_uname)
        except:
            f = ""
        if not f:
            return
        web.header('Content-type', 'image/jpeg')
        return f.read()


class Teams:
    def GET(self, team_id=""):
        print "GET Teams"
        pp = {}
        if team_id:
            pp['team'] = corpdb.teams.find_one({"_id": ObjectId(team_id)})

            if pp['team']:
	            pp['team_members'] = corpdb.employees.find({"team_ids" : ObjectId(team_id) })
	            pp['managed_teams'] = corpdb.teams.find({"managing_team_ids" : pp['team']['_id'] })
	            if "managing_team_ids" in pp['team']:
	                pp['managing_teams'] = corpdb.teams.find({"_id" : { "$in" : pp['team']['managing_team_ids']}})

	            return render_template('teams/show.html', pp=pp)
            else:
	            print "team not found"
	            raise web.seeother('/teams')
        else:
            pp['teams'] = corpdb.teams.find()
            return render_template('teams/index.html', pp=pp)


    def POST(self):
        print "POST Teams index (search)"
        form = web.input()
        print form
        team = corpdb.teams.find_one({"_id" : ObjectId(form['search'])})
        print team
        if team is None:
		    raise web.seeother('/teams')
        else:
		    print "team found"
		    raise web.seeother('/teams/' + str(team['_id']))


class EditTeam:
    @require_manager
    def GET(self, team_id):
        print "GET EditTeam"
        pp = {}
        pp['team'] = corpdb.teams.find_one({"_id": ObjectId(team_id)})
        pp['teams'] = corpdb.teams.find({"_id": {"$ne": ObjectId(team_id)}})
        print pp['teams']

        if pp['team'] is None:
            print "team is none"
            raise web.seeother('/teams')
        else:
            return render_template('teams/edit.html', pp=pp)

    @require_manager
    def POST(self, team_id):
        print "POST EditTeam"
        form = web.input(managing_team_ids=[])
        print form
        team = corpdb.teams.find_one({"_id": ObjectId(team_id) })

        # Name cannot be blank
        if len(form['name']) > 0:
            #if corpdb.teams.find({"_id": ObjectId(team_id)})
            team['name'] = form['name'].capitalize() 
            team['managing_team_ids'] = map(lambda id: ObjectId(id), form['managing_team_ids'])
            corpdb.teams.save(team)
            raise web.seeother('/teams/' + str(team['_id']))
        else:
            raise web.seeother('/teams')


class NewTeam:
    @require_manager
    def GET(self):
        print "GET NewTeam"
        return render_template('teams/new.html')

    @require_manager
    def POST(self):
        print "POST NewTeam"
        form = web.input()
        if len(form['name']) > 0:
            # make sure there are no other teams with this name
            team = corpdb.teams.find_one({"name": form['name']})
            if not team:
                team = {'name': form['name'].capitalize() }
                objectid = corpdb.teams.insert(team)
                raise web.seeother('/teams/' + str(objectid) + "/edit")
            else:
                raise web.seeother('/teams/' + str(team['_id']))
        else:
            raise web.seeother('/teams')


class DeleteTeam:
    #@require_manager
    def POST(self, team_id):
        print "POST DeleteTeam"
        corpdb.employees.update({"team_ids" : ObjectId(team_id)}, {"$pull": {"team_ids": ObjectId(team_id) }}, upsert=False, multi=True)
        corpdb.teams.update({"managing_team_ids" : ObjectId(team_id)}, {"$pull": {"managing_team_ids": ObjectId(team_id) }}, upsert=False, multi=True)
        corpdb.teams.remove(ObjectId(team_id))
        raise web.seeother('/teams')


class SkillGroups:
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
	            return render_template('skillgroups/show.html', pp=pp)

            else:
                print "skill not found"
                raise web.seeother('/skillgroups')
        else:
            pp['skill_groups'] = corpdb.skill_groups.find()
            return render_template('skillgroups/index.html', pp=pp)

    #@require_manager
    def POST(self):
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


class EditSkillGroup:
     #@require_manager
     def GET(self, skill_group_id):
         print "GET EditSkillGroup"
         pp = {}
         pp['skill_group'] = corpdb.skill_groups.find_one(ObjectId(skill_group_id))
         if pp['skill_group']:
             return render_template("skillgroups/edit.html", pp=pp)
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


class Skills:
    def GET(self, skill_id=""):
        print "GET Skills"
        pp = {}
        if skill_id:
            pp['skill'] = corpdb.skills.find_one(ObjectId(skill_id))

            #current_user = corpdb.employees.find_one({"user_id" : web.cookies()['auth_user']})
            pp['current_user_role'] = "manager"#current_user['role']

            if pp['skill']:
                pp['skill_groups'] = []
                pp['employees'] = []
                pp['skill_groups'] = corpdb.skill_groups.find({"_id" : { "$in" : pp['skill']['groups']}})
                pp['employees'] = corpdb.employees.find({"skills."+ str(pp['skill']['_id']): {"$exists":True} })
                return render_template('skills/show.html', pp=pp)

            else:
                print "skill not found"
                raise web.seeother('/skills')
        else:
            pp['skills'] = corpdb.skills.find()
            return render_template('skills/index.html', pp=pp)


    def POST(self):
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


class EditSkill:
     @require_manager
     def GET(self, skill_id):
         print "GET EditSkill"
         pp = {}
         pp['skill'] = corpdb.skills.find_one(ObjectId(skill_id))
         if pp['skill']:
             pp['skill_groups'] = corpdb.skill_groups.find()
             return render_template("skills/edit.html", pp=pp)
         else:
             raise web.seeother('/skills')

     @require_manager
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


class NewSkill:
    @require_manager
    def GET(self):
        print "GET NewSkill"
        return render_template('skills/new_skill.html')

    @require_manager
    def POST(self):
        print "POST NewSkill"
        form = web.input()
        if len(form['name']) > 0:
            # make sure there are no other skills with this name
            skill = corpdb.skills.find_one({"name": form['name']})
            if not skill:
                skill = {'name': form['name'].upper() }
                objectid = corpdb.skills.insert(skill)
                raise web.seeother('/skills/' + str(objectid) + "/edit")
            print "skill found"
            raise web.seeother('/skills/' + str(skill['_id']) + "/edit")
        raise web.seeother('/skills')


class DeleteSkill:
    #@require_manager
    def POST(self, skill_id):
        print "POST DeleteSkill"
        corpdb.employees.update({"skills."+ skill_id: {"$exists":True} }, {"$unset": {"skills."+ skill_id: 1}}, upsert=False, multi=True)
        corpdb.skills.remove(ObjectId(skill_id))
        raise web.seeother('/skills')

# LOCAL
if __name__ == "__main__":
    app = web.application(urls, globals())
    app.run()
