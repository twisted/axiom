from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import integer, reference, AND

class Referee(Item):
    schemaVersion = 1
    typeName = "test_reference_referee"

    topSecret = integer()

class SimpleReferent(Item):
    schemaVersion = 1
    typeName = "test_reference_referent"

    ref = reference()

class SomeException(Exception):
    pass

class AnotherException(SomeException):
    pass

class BadReferenceTestCase(TestCase):
    exceptions = (SomeException, AnotherException, ZeroDivisionError, ValueError)
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

    def _makeReferentItem(self, whenDeleted, unique):
        class _Referent(Item):
            schemaVersion = 1
            typeName = "test_reference_referent_%r" % unique

            ref = reference(whenDeleted=whenDeleted)

        return _Referent

    def testBadReferenceRaises(self):
        store = Store()
        for (i, exc) in enumerate(self.exceptions):
            MyReferent = self._makeReferentItem(exc, i)
            referee = Referee(store=store)
            referent = MyReferent(store=store, ref=referee)
            referee.deleteFromStore()
            del referee

            (referent,) = list(store.query(MyReferent))
            self.assertRaises(exc, lambda: referent.ref)
            referent.deleteFromStore()

    def testBadReferenceNone(self):
        store = Store()
        referee = Referee(store=store, topSecret=0)
        MyReferent = self._makeReferentItem(None, None)
        referent = MyReferent(store=store, ref=referee)
        referee.deleteFromStore()
        del referee

        (referent,) = list(store.query(MyReferent))
        self.assertEqual(referent.ref, None)

    testBadReferenceRaises.todo = testBadReferenceNone.todo = 'No behavior yet defined for bad references'

    def testReferenceQuery(self):
        from axiom.test import oldapp
        store = Store()
        oldapp.Sword(store=store)
        list(store.query(oldapp.Sword, oldapp.Player.sword == oldapp.Sword.storeID))

    testReferenceQuery.todo = 'No behaviour yet defined for querying unfulfilled references'
