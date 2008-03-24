# -*- test-case-name: axiom.test.test_upgrading.DuringUpgradeTests.test_reentrantUpgraderFailure -*-

from axiom.attributes import integer, reference
from axiom.item import Item, normalize
from axiom.upgrade import registerUpgrader

class Simple(Item):
    # Don't import the old schema. -exarkun
    typeName = normalize(
        "axiom.test.upgrade_fixtures.reentrant_old.Simple")
    schemaVersion = 2
    dummy = integer()
    selfReference = reference()

def upgradeSimple1to2(old):
    # Force the upgrade.
    selfRef = old.store.getItemByID(old.storeID)
    return old.upgradeVersion(
        old.typeName, 1, 2,
        dummy=old.dummy,
        selfReference=selfRef)

registerUpgrader(upgradeSimple1to2, Simple.typeName, 1, 2)
