
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
