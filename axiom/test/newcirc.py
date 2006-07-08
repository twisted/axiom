# -*- test-case-name: axiom.test.test_upgrading.DeletionTest.testCircular -*-
from axiom.item import Item

from axiom.attributes import reference, integer

class A(Item):
    typeName = 'test_circular_a'
    b = reference()

class B(Item):
    typeName = 'test_circular_b'
    a = reference()
    n = integer()

    schemaVersion = 2

from axiom.upgrade import registerUpgrader

def b1to2(oldb):
    # This upgrader isn't doing anything that actually makes sense; in a
    # realistic upgrader, you'd probably be changing A around, perhaps deleting
    # it to destroy old adjunct items and creating a new A.  The point is,
    # s.findUnique(A).b should give back the 'b' that you are upgrading whether
    # it is run before or after the upgrade.
    oldb.a.deleteFromStore()
    newb = oldb.upgradeVersion('test_circular_b', 1, 2)
    newb.n = oldb.n
    newb.a = A(store=newb.store,
               b=newb)
    return newb

registerUpgrader(b1to2, 'test_circular_b', 1, 2)
