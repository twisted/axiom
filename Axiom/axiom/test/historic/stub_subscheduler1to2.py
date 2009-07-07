# test-case-name: axiom.test.historic.test_subscheduler1to2

"""
Database creator for the test for the upgrade of SubScheduler from version 1 to
version 2.
"""

from axiom.test.historic.stubloader import saveStub

from axiom.scheduler import SubScheduler
from axiom.dependency import installOn


def createDatabase(store):
    installOn(SubScheduler(store=store), store)


if __name__ == '__main__':
    saveStub(createDatabase, 17606)
