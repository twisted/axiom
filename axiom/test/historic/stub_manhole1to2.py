# -*- test-case-name: axiom.test.historic.test_manhole1to2 -*-
# Copyright 2008 Divmod, Inc.  See LICENSE for details.

from axiom.dependency import installOn
from axiom.batch import BatchManholePowerup
from axiom.test.historic.stubloader import saveStub

def createDatabase(store):
    installOn(BatchManholePowerup(store=store), store)

if __name__ == '__main__':
    saveStub(createDatabase, 16829)
