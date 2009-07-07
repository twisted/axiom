# -*- test-case-name: axiom.test.historic.test_parentHook3to4 -*-

"""
Generate a test stub for upgrading L{_SubSchedulerParentHook} from version 3 to
4, which removes the C{scheduler} attribute.
"""

from axiom.test.historic.stubloader import saveStub

from axiom.dependency import installOn
from axiom.scheduler import Scheduler, _SubSchedulerParentHook
from axiom.substore import SubStore

def createDatabase(store):
    scheduler = Scheduler(store=store)
    installOn(scheduler, store)
    installOn(
        _SubSchedulerParentHook(
            store=store, loginAccount=SubStore(store=store)),
        store)


if __name__ == '__main__':
    saveStub(createDatabase, 17606)
