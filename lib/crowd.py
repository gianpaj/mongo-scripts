
import os
import suds

here = os.path.dirname(os.path.abspath(__file__))
url='file://' + here + '/crowd-fixed.wsdl'

class Crowd:
    def __init__(self,user,pwd):
        self.client = suds.client.Client(url)

        self.auth_context = self.client.factory.create('ns1:ApplicationAuthenticationContext')
        self.auth_context.name = user
        self.auth_context.credential.credential = pwd

        self.token = self.client.service.authenticateApplication(self.auth_context)

        self.service = self.client.service
        


    def isValidPrincipalToken(self,token):
        return self.service.isValidPrincipalToken( self.token , token , self.factory.create( "ns1:ArrayOfValidationFactor" ) )
    
    def invalidatePrincipalToken(self,token):
        self.service.invalidatePrincipalToken( self.token , token )

    def authenticatePrincipalSimple(self,username,password):
        return self.service.authenticatePrincipalSimple( self.token , username , password )

    def findGroupByName(self,group):
        return self.service.findGroupByName( self.token , group ).members[0]


    def findPrincipalByName(self,name):
        return self.service.findPrincipalByName( self.token , name )

    def getUser(self,name):
        p = self.findPrincipalByName( name )
        if p == None:
            return None
        
        m = { "username" : name }

        for x in p.attributes[0]:
            a = x.values[0]
            if len(a) == 1:
                m[x.name] = a[0]
            else:
                m[x.name] = a

        return m
