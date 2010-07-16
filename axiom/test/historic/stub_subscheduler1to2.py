# test-case-name: axiom.test.historic.test_subscheduler1to2

"""
Database creator for the test for the upgrade of SubScheduler from version 1 to
version 2.
"""

from axiom.test.historic.stubloader import saveStub

from axiom.substore import SubStore
from axiom.scheduler import SubScheduler
from axiom.dependency import installOn


def createDatabase(store):
    sub = SubStore.createNew(store, ["substore"]).open()
    installOn(SubScheduler(store=sub), sub)


if __name__ == '__main__':
    saveStub(createDatabase, 17606)
