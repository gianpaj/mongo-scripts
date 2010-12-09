from settings_private import *

import os
here = os.path.dirname(os.path.abspath(__file__))
devel = os.path.exists(os.path.join(here, 'devel'))

if devel:
    usagedb_host = wwwdb_host = mongowwwdb_host = "localhost"
else:
    usagedb_host = "jira.10gen.cc"
    wwwdb_host = "www-c.10gen.cc"
    mongowwwdb_host = "www-m1.10gen.cc"
