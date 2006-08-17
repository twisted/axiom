import gc

from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import integer, reference

class Referee(Item):
    schemaVersion = 1
    typeName = "test_reference_referee"

    topSecret = integer()

class SimpleReferent(Item):
    schemaVersion = 1
    typeName = "test_reference_referent"

    ref = reference()

class DependentReferent(Item):
    ref = reference(whenDeleted=reference.CASCADE, reftype=Referee)

class BadReferenceTestCase(TestCase):
    ntimes = 10

    def testSanity(self):
        store = Store()
        for i in xrange(self.ntimes):
            SimpleReferent(store=store, ref=Referee(store=store, topSecret=i))
            (referee,) = list(store.query(Referee))
            (referent,) = list(store.query(SimpleReferent))
            self.assertEqual(referent.ref.topSecret, referee.topSecret)
            referee.deleteFromStore()
            referent.deleteFromStore()

    def testBadReferenceNone(self):
        store = Store()
        referee = Referee(store=store, topSecret=0)
        referent = SimpleReferent(store=store, ref=referee)
        referee.deleteFromStore()

        referee = None
        gc.collect()

        (referent,) = list(store.query(SimpleReferent))
        self.assertEqual(referent.ref, None)

    def testBadReferenceNoneRevert(self):
        store = Store()
        referee = Referee(store=store, topSecret=0)
        referent = SimpleReferent(store=store, ref=referee)
        def txn():
            referee.deleteFromStore()
            self.assertEqual(referent.ref, None)
            1 / 0
        self.assertRaises(ZeroDivisionError, store.transact, txn)
        self.assertEqual(referent.ref, referee)

        referent = None
        referee = None
        gc.collect()

        referent = store.findUnique(SimpleReferent)
        referee = store.findUnique(Referee)
        self.assertEqual(referent.ref, referee)

    def testReferenceQuery(self):
        store = Store()
        referee = Referee(store=store, topSecret=0)
        self.assertEqual(
            list(store.query(SimpleReferent,
                             SimpleReferent.ref == Referee.storeID)),
            [])

    def testReferenceDeletion(self):
        store = Store()
        referee = Referee(store=store, topSecret=0)
        dep = DependentReferent(store=store,
                                ref=referee)
        sid = dep.storeID
        self.assertIdentical(store.getItemByID(sid), dep) # sanity
        referee.deleteFromStore()
        self.assertRaises(KeyError, store.getItemByID, sid)
