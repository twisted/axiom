import gc

from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.upgrade import registerUpgrader, registerAttributeCopyingUpgrader
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
        for i in range(self.ntimes):
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


    def test_brokenReferenceException(self):
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
        self.patch(BreakingReferent.ref, 'whenDeleted', reference.CASCADE)
        self.assertRaises(BrokenReference, lambda: referent.ref)


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
            "{!r} was instance of {!r}, expected {!r}".format(newReferee,
                                                    type(newReferee),
                                                    UpgradedItem))


    def test_dummyItemReferenceUpgraded(self):
        """
        Getting the value of a reference attribute which has been set to a
        legacy item, which is then upgraded while the reference is "live",
        results in an instance of the most recent type for that item.
        """
        store = Store()
        referent = SimpleReferent(store=store)
        oldReferee = nonUpgradedItem2(store=store)
        referent.ref = oldReferee
        # Manually run the upgrader on this specific legacy item. This is the
        # same as if the SimpleReferent item had been created in an upgrader
        # for UpgradedItem, except that we can keep a strong reference to
        # oldReferee to ensure it is not garbage collected (this would
        # otherwise happen nondeterministically on platforms like PyPy).
        newReferee = item2to3(oldReferee)
        self.assertIsInstance(newReferee, UpgradedItem)
        self.assertIdentical(referent.ref, newReferee)


    def test_dummyItemReferenceInUpgrade(self):
        """
        Setting the value of a reference attribute to a legacy item during an
        upgrade results in the same value being set on the upgraded item.
        """
        store = Store()
        def tx():
            oldReferent = nonUpgradedItem(store=store)
            oldReferee = nonUpgradedItem(store=store)
            newReferent = oldReferent.upgradeVersion(
                UpgradedItem.typeName, 1, 2)
            newReferee = oldReferee.upgradeVersion(
                UpgradedItem.typeName, 1, 2, ref=newReferent)
            self.assertIdentical(newReferee.ref, newReferent)
        store.transact(tx)


    def test_dummyItemGetItemByID(self):
        """
        Instantiating a dummy item and then getting it by its storeID should
        upgrade it.
        """
        store = Store()
        t = nonUpgradedItem(store=store)
        self.assertEqual(t.__legacy__, True)
        self.assertRaises(KeyError, store.objectCache.get, t.storeID)
        t2 = store.getItemByID(t.storeID)
        self.assertNotIdentical(t, t2)
        self.assertTrue(isinstance(t2, UpgradedItem))



class UpgradedItem(Item):
    """
    A simple item which is the current version of L{nonUpgradedItem}.
    """
    schemaVersion = 3
    ref = reference()



nonUpgradedItem = declareLegacyItem(
    UpgradedItem.typeName, 1,
    dict(ref=reference()))



nonUpgradedItem2 = declareLegacyItem(
    UpgradedItem.typeName, 2,
    dict(ref=reference()))

registerAttributeCopyingUpgrader(UpgradedItem, 1, 2)


def item2to3(old):
    """
    Upgrade an nonUpgradedItem to UpgradedItem
    """
    return old.upgradeVersion(UpgradedItem.typeName, 2, 3, ref=old.ref)

registerUpgrader(item2to3, UpgradedItem.typeName, 2, 3)
