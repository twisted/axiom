# -*- test-case-name: axiom.test.historic.test_parentHook2to3 -*-
"""
Generate a test stub for upgrading L{_SubSchedulerParentHook} from version 2 to
3, which removes the C{scheduledAt} attribute.
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
    saveStub(createDatabase, 16800)
