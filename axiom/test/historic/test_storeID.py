from axiom.test.historic.stubloader import StubbedTest
from axiom.errors import ItemNotFound
from axiom.test.historic.stub_storeID import Dummy



class StoreIDTransitionTest(StubbedTest):
    def test_transition(self):
        """
        Test that the items survived the transition.
        """
        self.assertEquals(self.store.getItemByID(1).attribute, u'one')
        self.assertEquals(
            self.store.findUnique(Dummy, Dummy.attribute == u'two').storeID,
            2)
        self.assertRaises(ItemNotFound, self.store.getItemByID, 3)
        self.assertEquals(self.store.getItemByID(4).attribute, u'four')


    def test_vacuum(self):
        """
        Test that the items survive vacuuming.
        """
        self.store.executeSQL('VACUUM')
        self.test_transition()
