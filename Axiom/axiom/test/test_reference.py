import gc

from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import integer, reference
from axiom.errors import BrokenReference

from axiom.test.test_upgrading import axiomInvalidate

class Referee(Item):
    schemaVersion = 1
    typeName = "test_reference_referee"

    topSecret = integer()

class SimpleReferent(Item):
    schemaVersion = 1
    typeName = "test_reference_referent"

    ref = reference()


class BreakingReferent(Item):
    schemaVersion = 1
    typeName = "test_reference_breaking_referent"

    ref = reference(whenDeleted=reference.NULLIFY)

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
        """
        Test that accessing a broken reference on an Item that has already been
        loaded into memory correctly nullifies the attribute.
        """
        store = Store()
        referee = Referee(store=store, topSecret=0)
        referent = SimpleReferent(store=store, ref=referee)
        referee.deleteFromStore()

        referee = None
        gc.collect()

        (referent,) = list(store.query(SimpleReferent))
        self.assertEqual(referent.ref, None)

    def testBadReferenceNoneLoading(self):
        """
        Test that accessing a broken reference on an Item that has not yet been
        loaded correctly nullifies the attribute.
        """
        store = Store()
        referee = Referee(store=store, topSecret=0)
        referent = SimpleReferent(store=store, ref=referee)
        referee.deleteFromStore()

        referee = None
        referent = None
        gc.collect()

        (referent,) = list(store.query(SimpleReferent))
        self.assertEqual(referent.ref, None)


    def testBrokenReferenceException(self):
        """
        Test that an exception is raised when a broken reference is detected
        when this should be impossible (ie. CASCADE or NULLIFY).
        """
        store = Store()

        referee = Referee(store=store, topSecret=0)
        referent = BreakingReferent(store=store, ref=referee)

        referee.deleteFromStore()
        referent = None
        gc.collect()

        referent = store.findFirst(BreakingReferent)
        BreakingReferent.ref.whenDeleted = reference.CASCADE
        self.assertRaises(BrokenReference, lambda: referent.ref)
        BreakingReferent.ref.whenDeleted = reference.NULLIFY

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

    def testBatchReferenceDeletion(self):
        """
        Test that batch deletion removes dependent items correctly.
        """
        store = Store()
        referee = Referee(store=store, topSecret=0)
        dep = DependentReferent(store=store,
                                ref=referee)
        sid = dep.storeID
        store.query(Referee).deleteFromStore()
        self.assertRaises(KeyError, store.getItemByID, sid)
