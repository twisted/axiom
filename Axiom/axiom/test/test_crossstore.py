
from axiom.store import Store
from axiom.substore import SubStore
from axiom.item import Item

from axiom.attributes import integer

from twisted.trial.unittest import TestCase

class ExplosiveItem(Item):

    nothing = integer()

    def yourHeadAsplode(self):
        1 / 0

class TestCrossStoreTransactions(TestCase):
    def setUp(self):
        self.spath = self.mktemp() + ".axiom"
        self.store = Store(self.spath)
        self.substoreitem = SubStore.createNew(self.store,
                                               ["sub.axiom"])

        self.substore = self.substoreitem.open()
        # Not available yet.
        self.substore.attachToParent()

    def testCrossStoreTransactionality(self):
        def createTwoSubStoreThings():
            ExplosiveItem(store=self.store)
            ei = ExplosiveItem(store=self.substore)
            ei.yourHeadAsplode()

        self.failUnlessRaises(ZeroDivisionError,
                              self.store.transact,
                              createTwoSubStoreThings)

        self.failUnlessEqual(
            self.store.query(ExplosiveItem).count(),
            0)

        self.failUnlessEqual(
            self.substore.query(ExplosiveItem).count(),
            0)


