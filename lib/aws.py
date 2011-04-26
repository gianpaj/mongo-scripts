
from boto.ses import SESConnection

import aws_settings

def send_email( source , subject , body , to ):
    connection = SESConnection( aws_settings.key , aws_settings.secret )
    connection.send_email( source , subject , body , to )


