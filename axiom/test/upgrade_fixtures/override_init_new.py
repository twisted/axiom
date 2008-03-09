# -*- test-case-name: axiom.test.test_upgrading.DuringUpgradeTests.test_overridenInitializerInUpgrader -*-

from axiom.attributes import integer, inmemory
from axiom.item import Item
from axiom.upgrade import registerAttributeCopyingUpgrader

from axiom.test.upgrade_fixtures.override_init_old import Simple as OldSimple

class Simple(Item):
    typeName = OldSimple.typeName
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
