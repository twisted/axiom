# -*- test-case-name: axiom.test.test_upgrading.DuringUpgradeTests.test_overridenInitializerInUpgrader -*-

from axiom.attributes import integer, inmemory
from axiom.item import Item, normalize
from axiom.upgrade import registerAttributeCopyingUpgrader

class Simple(Item):
    # Don't import the old version, otherwise its schema will get loaded.  This
    # is valid in the upgrade tests, but not at other times. -exarkun
    typeName = normalize(
        "axiom.test.upgrade_fixtures.override_init_old.Simple")
    schemaVersion = 2

    dummy = integer()
    verify = inmemory()

    def __init__(self, **stuff):
        """
        Override Item's __init__ to re-retrieve this Item from the store.
        """
        Item.__init__(self, **stuff)
        self.verify = (self, self.store.getItemByID(self.storeID))

registerAttributeCopyingUpgrader(Simple, 1, 2)
