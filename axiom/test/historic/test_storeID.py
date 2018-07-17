import gc

from axiom.test.historic.stubloader import StubbedTest
from axiom.errors import ItemNotFound
from axiom.item import Item
from axiom.attributes import text
from axiom.upgrade import registerAttributeCopyingUpgrader


class Dummy(Item):
    typeName = 'axiom_storeid_dummy'
    schemaVersion = 2

    attribute = text(doc='text', allowNone=False)


registerAttributeCopyingUpgrader(Dummy, 1, 2)


class Dummy2(Item):
    typeName = 'axiom_storeid_dummy2'
    schemaVersion = 2

    attribute = text(doc='text', allowNone=False)


registerAttributeCopyingUpgrader(Dummy2, 1, 2)



class StoreIDTransitionTest(StubbedTest):
    def test_transition(self):
        """
        Test that the items survived the transition to explicit oids.
        """
        # Make sure we push the upgraded items out of cache
        gc.collect()

        self.assertEquals(self.store.getItemByID(1).attribute, u'one')
        i = self.store.findUnique(Dummy, Dummy.attribute == u'two')
        self.assertEquals(i.storeID, 2)
        self.assertRaises(ItemNotFound, self.store.getItemByID, 3)
        i.deleteFromStore()
        i2 = self.store.getItemByID(4)
        self.assertEquals(i2.attribute, u'four')
        self.assertIsInstance(i2, Dummy2)


    def test_vacuum(self):
        """
        Test that the items survive vacuuming.
        """
        # Make sure we push the upgraded items out of cache
        gc.collect()
        self.store.executeSQL('VACUUM')
        self.test_transition()
