# -*- test-case-name: axiom.test.historic.test_parentHook1to2 -*-

"""
Create a stub database to test the upgrade of L{_SubSchedulerParentHook} to add
the C{scheduler} attribute.
"""

from axiom.test.historic.stubloader import saveStub

from axiom.scheduler import Scheduler, _SubSchedulerParentHook
from axiom.dependency import installOn

def createDatabase(store):
    installOn(Scheduler(store=store), store)
    _SubSchedulerParentHook(store=store)


if __name__ == '__main__':
    saveStub(createDatabase, 11022)
