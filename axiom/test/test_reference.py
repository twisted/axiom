import gc

from twisted.trial.unittest import TestCase
from twisted.internet.utils import runWithWarningsSuppressed

from epsilon.hotfix import require

require('twisted', 'trial_assertwarns')

from axiom.store import Store
from axiom.upgrade import registerUpgrader
from axiom.item import Item, declareLegacyItem
from axiom.attributes import integer, reference
from axiom.errors import BrokenReference, DeletionDisallowed

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

class DisallowReferent(Item):
    ref = reference(whenDeleted=reference.DISALLOW, reftype=Referee)

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


    def test_brokenReferenceWarning(self):
        """
        Accessing a broken reference with both C{NULLIFY} and C{allowNone=False}
        should return C{None}, and produce a C{DeprecationWarning}.
        """
        class InconsistentReferenceItem(Item):
            ref = runWithWarningsSuppressed(
                [(('ignore',), dict(
                    message='whenDeleted=NULLIFY conflicts with allowNone=False',
                    category=DeprecationWarning))],
                lambda: reference(allowNone=False, whenDeleted=reference.NULLIFY))

        s = Store()
        def txn():
            referee = Referee(store=s)
            referent = InconsistentReferenceItem(store=s, ref=referee)
            referee.deleteFromStore()
            return referee.storeID
        deletedStoreID = s.transact(txn)

        referent = s.findUnique(InconsistentReferenceItem)
        self.assertWarns(
            DeprecationWarning,
            ('broken reference with NULLIFY and allowNone=False to storeID %r'
                % (deletedStoreID,)),
            __file__,
            lambda: referent.ref)


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

    def testBrokenReferenceDisallow(self):
        """
        Test that deleting an item referred to by a whenDeleted == DISALLOW
        reference raises an exception.
        """
        store = Store()
        referee = Referee(store=store, topSecret=0)
        referent = DisallowReferent(store=store, ref=referee)

        self.assertRaises(DeletionDisallowed, referee.deleteFromStore)
        self.assertRaises(DeletionDisallowed, store.query(Referee).deleteFromStore)

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


    def test_dummyItemReference(self):
        """
        Getting the value of a reference attribute which has previously been
        set to a legacy item results in an instance of the most recent type for
        that item.
        """
        store = Store()
        referent = SimpleReferent(store=store)
        oldReferee = nonUpgradedItem(store=store)
        referent.ref = oldReferee
        newReferee = referent.ref
        self.assertTrue(
            isinstance(newReferee, UpgradedItem),
            "%r was instance of %r, expected %r" % (newReferee,
                                                    type(newReferee),
                                                    UpgradedItem))

    def test_dummyItemGetItemByID(self):
        """
        Instantiating a dummy item and then getting it by its storeID should
        upgrade it.
        """
        store = Store()
        t = nonUpgradedItem(store=store)
        self.assertEquals(t.__legacy__, True)
        self.assertFalse(store.objectCache.has(t.storeID))
        t2 = store.getItemByID(t.storeID)
        self.assertNotIdentical(t, t2)
        self.assertTrue(isinstance(t2, UpgradedItem))


    def test_whenDeletedTypeError(self):
        """
        Passing L{reference} an invalid value for C{whenDeleted} should raise a
        C{TypeError}.
        """
        for bad in [None, 0, 'NULLIFY']:
            e = self.assertRaises(
                TypeError,
                lambda: reference(whenDeleted=bad))
            self.assertEquals(
                str(e),
                'whenDeleted must be one of: '
                'reference.NULLIFY, reference.CASCADE, reference.DISALLOW')


    def test_nullifyDisallowNoneConflict(self):
        """
        Creating a L{reference} attribute that both forbids C{None}s and allows
        its referent to be deleted should produce a C{DeprecationWarning}.
        """
        self.assertWarns(
            DeprecationWarning,
            'whenDeleted=NULLIFY conflicts with allowNone=False',
            __file__,
            lambda: reference(
                allowNone=False,
                whenDeleted=reference.NULLIFY))



class UpgradedItem(Item):
    """
    A simple item which is the current version of L{nonUpgradedItem}.
    """
    schemaVersion = 2
    dummy = integer()



nonUpgradedItem = declareLegacyItem(
    UpgradedItem.typeName, 1,
    dict(dummy=integer()))



def item1to2(old):
    """
    Upgrade an nonUpgradedItem to UpgradedItem
    """
    return old.upgradeVersion(UpgradedItem.typeName, 1, 2, dummy=old.dummy)

registerUpgrader(item1to2, UpgradedItem.typeName, 1, 2)
