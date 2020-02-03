import gc

from axiom.test.historic.stubloader import StubbedTest
from axiom.errors import ItemNotFound
from axiom.item import Item
from axiom.attributes import text
from axiom.upgrade import (
    registerAttributeCopyingUpgrader, upgradeExplicitOid, _hasExplicitOid)


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
        # Make sure we push the upgraded items out of cache
        gc.collect()

        self.assertEquals(self.store.getItemByID(1).attribute, u'one')
        self.assertEquals(
            self.store.findUnique(Dummy, Dummy.attribute == u'two').storeID,
            2)
        self.assertRaises(ItemNotFound, self.store.getItemByID, 3)
        i2 = self.store.getItemByID(4)
        self.assertEquals(i2.attribute, u'four')
        self.assertIsInstance(i2, Dummy2)


    def test_vacuum(self):
        """
        Test that the items survive vacuuming after upgrading.
        """
        # This will upgrade Dummy2 in-place; Dummy had its own upgrade.
        upgradeExplicitOid(self.store)

        # Make sure we push the upgraded items out of cache
        gc.collect()
        self.store.executeSQL('VACUUM')
        self.test_transition()


    def test_upgradeOid(self):
        """
        When an item type is upgraded, the new table has an explicit oid
        column.
        """
        self.assertTrue(
            _hasExplicitOid(self.store, 'item_axiom_storeid_dummy_v2'))
        self.assertFalse(
            _hasExplicitOid(self.store, 'item_axiom_storeid_dummy2_v1'))


    def test_oids(self):
        """
        Explicit oid columns are added to tables by L{upgradeExplicitOid}.
        """
        upgradeExplicitOid(self.store)
        self.assertTrue(_hasExplicitOid(self.store, 'axiom_objects'))
        self.assertTrue(_hasExplicitOid(self.store, 'axiom_types'))
        self.assertTrue(
            _hasExplicitOid(self.store, 'item_axiom_storeid_dummy_v2'))
        self.assertTrue(
            _hasExplicitOid(self.store, 'item_axiom_storeid_dummy2_v1'))
