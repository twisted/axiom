# -*- test-case-name: axiom.test.test_xatop.ProcessConcurrencyTestCase -*-

# this file is in support of the named test case

import sys

from axiom.store import Store
from twisted.python import filepath

# Open the store so that we get the bad version of the schema
s = Store(filepath.FilePath(sys.argv[1]))

# Alert our parent that we did that
sys.stdout.write("1")
sys.stdout.flush()

# Grab the storeID we are supposed to be reading
sids = sys.stdin.readline()
sid = int(sids)

# load the item we were told to - this should force a schema reload
s.getItemByID(sid)

# let our parent process know that we loaded it successfully
sys.stdout.write("2")
sys.stdout.flush()

# then terminate cleanly
