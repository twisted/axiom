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
    schemaVersion = 1

    attribute = text(doc='text', allowNone=False)



class StoreIDTransitionTest(StubbedTest):
    def test_transition(self):
        """
        Test that the items survived the transition to explicit oids.
        """
        self.assertEquals(self.store.getItemByID(1).attribute, u'one')
        self.assertEquals(
            self.store.findUnique(Dummy, Dummy.attribute == u'two').storeID,
            2)
        self.assertRaises(ItemNotFound, self.store.getItemByID, 3)
        i = self.store.getItemByID(4)
        self.assertEquals(i.attribute, u'four')
        self.assertIsInstance(i, Dummy2)


    def test_vacuum(self):
        """
        Test that the items survive vacuuming.
        """
        self.store.executeSQL('VACUUM')
        self.test_transition()
