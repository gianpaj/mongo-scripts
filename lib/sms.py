
import twilio.rest
import settings

class Twilio(object):
    """
    t = sms.Twilio()
    t.sms( "+16462567013" , "hi eliot" )
    """

    def __init__(self,sid=None,token=None,from_="+16504904704"):
        if sid is None:
            import settings
            sid = settings.twilio_sid
            token = settings.twilio_token
            
        self.client = twilio.rest.TwilioRestClient( sid , token )
        
        self.from_ = from_

    def sms(self,to,body):
        return self.client.sms.messages.create( to=to, from_=self.from_ , body=body )
