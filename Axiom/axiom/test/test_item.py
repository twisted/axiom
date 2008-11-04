
import sys, os

from twisted.trial import unittest
from twisted.trial.unittest import TestCase
from twisted.internet import error, protocol, defer, reactor
from twisted.protocols import policies
from twisted.python import log, filepath

from axiom import store, item
from axiom.store import Store
from axiom.item import Item, declareLegacyItem
from axiom.errors import ChangeRejected
from axiom.test import itemtest, itemtestmain
from axiom.attributes import integer, text, inmemory

class ProcessFailed(Exception):
    pass

class ProcessOutputCollector(protocol.ProcessProtocol, policies.TimeoutMixin):
    TIMEOUT = 60

    def __init__(self, onCompletion):
        self.output = []
        self.error = []
        self.onCompletion = onCompletion
        self.onCompletion.addCallback(self.processOutput)

    def processOutput(self, output):
        return output

    def timeoutConnection(self):
        self.transport.signalProcess('KILL')

    def connectionMade(self):
        self.setTimeout(self.TIMEOUT)

    def outReceived(self, bytes):
        self.resetTimeout()
        self.output.append(bytes)

    def errReceived(self, bytes):
        self.resetTimeout()
        self.error.append(bytes)

    def processEnded(self, reason):
        self.setTimeout(None)
        if reason.check(error.ProcessTerminated):
            self.onCompletion.errback(ProcessFailed(self, reason))
        elif self.error:
            self.onCompletion.errback(ProcessFailed(self, None))
        else:
            self.onCompletion.callback(self.output)



class NoAttrsItem(item.Item):
    typeName = 'noattrsitem'
    schemaVersion = 1



class TransactedMethodItem(item.Item):
    """
    Helper class for testing the L{axiom.item.transacted} decorator.
    """
    value = text()
    calledWith = inmemory()

    def method(self, a, b, c):
        self.value = u"changed"
        self.calledWith = [a, b, c]
        raise Exception("TransactedMethodItem.method test exception")
    method.attribute = 'value'
    method = item.transacted(method)



class StoredNoticingItem(item.Item):
    """
    Test item which just remembers whether or not its C{stored} method has been
    called.
    """
    storedCount = integer(doc="""
    The number of times C{stored} has been called on this item.
    """, default=0)

    activatedCount = integer(doc="""
    The number of times C{stored} has been called on this item.
    """, default=0)

    activated = inmemory(doc="""
    A value set in the C{activate} callback and nowhere else.  Used to
    determine the ordering of C{activate} and C{stored} calls.
    """)

    def activate(self):
        self.activated = True


    def stored(self):
        self.storedCount += 1
        self.activatedCount += getattr(self, 'activated', 0)


class ItemWithDefault(item.Item):
    """
    Item with an attribute having a default value.
    """
    value = integer(default=10)



class ItemTestCase(unittest.TestCase):
    """
    Tests for L{Item}.
    """

    def test_repr(self):
        """
        L{Item.__repr__} should return a C{str} giving the name of the
        subclass and the names and values of all the item's attributes.
        """
        reprString = repr(ItemWithDefault(value=123))
        self.assertIn('value=123', reprString)
        self.assertIn('storeID=None', reprString)
        self.assertIn('ItemWithDefault', reprString)

        store = Store()
        item = ItemWithDefault(store=store, value=321)
        reprString = repr(item)
        self.assertIn('value=321', reprString)
        self.assertIn('storeID=%d' % (item.storeID,), reprString)
        self.assertIn('ItemWithDefault', reprString)


    def test_partiallyInitializedRepr(self):
        """
        L{Item.__repr__} should return a C{str} giving some information,
        even if called before L{Item.__init__} has run completely.
        """
        item = ItemWithDefault.__new__(ItemWithDefault)
        reprString = repr(item)
        self.assertIn('ItemWithDefault', reprString)


    def test_itemClassOrdering(self):
        """
        Test that L{Item} subclasses (not instances) sort by the Item's
        typeName.
        """
        A = TransactedMethodItem
        B = NoAttrsItem

        self.failUnless(A < B)
        self.failUnless(B >= A)
        self.failIf(A >= B)
        self.failIf(B <= A)
        self.failUnless(A != B)
        self.failUnless(B != A)
        self.failIf(A == B)
        self.failIf(B == A)


    def test_legacyItemComparison(self):
        """
        Legacy items with different versions must not compare equal.
        """
        legacy1 = declareLegacyItem('test_type', 1, {})
        legacy2 = declareLegacyItem('test_type', 2, {})
        self.assertNotEqual(legacy1, legacy2)
        self.assertEqual(legacy1, legacy1)
        self.assertEqual(legacy2, legacy2)


    def testCreateItem(self):
        st = store.Store()
        self.assertRaises(item.CantInstantiateItem, item.Item, store=st)


    def testCreateItemWithDefault(self):
        """
        Test that attributes with default values can be set to None properly.
        """
        st = store.Store()
        it = ItemWithDefault()
        it.value = None
        self.assertEqual(it.value, None)


    def test_storedCallbackAfterActivateCallback(self):
        """
        Test that L{Item.stored} is only called after L{Item.activate} has been
        called.
        """
        st = store.Store()
        i = StoredNoticingItem(store=st)
        self.assertEquals(i.activatedCount, 1)


    def test_storedCallbackOnAttributeSet(self):
        """
        Test that L{Item.stored} is called when an item is actually added to a
        store and not before.
        """
        st = store.Store()
        i = StoredNoticingItem()
        self.assertEquals(i.storedCount, 0)
        i.store = st
        self.assertEquals(i.storedCount, 1)


    def test_storedCallbackOnItemCreation(self):
        """
        Test that L{Item.stored} is called when an item is created with a
        store.
        """
        st = store.Store()
        i = StoredNoticingItem(store=st)
        self.assertEquals(i.storedCount, 1)


    def test_storedCallbackNotOnLoad(self):
        """
        Test that pulling an item out of a store does not invoke its stored
        callback again.
        """
        st = store.Store()
        storeID = StoredNoticingItem(store=st).storeID
        self.assertEquals(st.getItemByID(storeID).storedCount, 1)


    def testTransactedTransacts(self):
        """
        Test that a method wrapped in C{axiom.item.transacted} is automatically
        run in a transaction.
        """
        s = store.Store()
        i = TransactedMethodItem(store=s, value=u"unchanged")
        exc = self.assertRaises(Exception, i.method, 'a', 'b', 'c')
        self.assertEquals(exc.args, ("TransactedMethodItem.method test exception",))
        self.assertEquals(i.value, u"unchanged")


    def testTransactedPassedArguments(self):
        """
        Test that position and keyword arguments are passed through
        L{axiom.item.transacted}-wrapped methods correctly.
        """
        s = store.Store()
        i = TransactedMethodItem(store=s)
        exc = self.assertRaises(Exception, i.method, 'a', b='b', c='c')
        self.assertEquals(exc.args, ("TransactedMethodItem.method test exception",))
        self.assertEquals(i.calledWith, ['a', 'b', 'c'])


    def testTransactedPreservesAttributes(self):
        """
        Test that the original function attributes are available on a
        L{axiom.item.transacted}-wrapped function.
        """
        self.assertEquals(TransactedMethodItem.method.attribute, 'value')


    def testPersistentValues(self):
        st = store.Store()
        pi = itemtest.PlainItem(store=st, plain=u'hello')
        self.assertEqual(pi.persistentValues(), {'plain': u'hello'})


    def testPersistentValuesWithoutValue(self):
        st = store.Store()
        pi = itemtest.PlainItem(store=st)
        self.assertEqual(pi.persistentValues(), {'plain': None})


    def testCreateItemWithNoAttrs(self):
        st = store.Store()
        self.assertRaises(store.NoEmptyItems, NoAttrsItem, store=st)

    def testCreatePlainItem(self):
        st = store.Store()
        s = itemtest.PlainItem(store=st)

    def testLoadLoadedPlainItem(self):
        """
        Test that loading an Item out of the store by its Store ID
        when a Python object representing that Item already exists in
        memory returns the same object as the one which already
        exists.
        """
        st = store.Store()
        item = itemtest.PlainItem(store=st)
        self.assertIdentical(item, st.getItemByID(item.storeID))

    def testLoadUnimportedPlainItem(self):
        """
        Test that an Item in the database can be loaded out of the
        database, even if the module defining its Python class has not
        been imported, as long as its class definition has not moved
        since it was added to the database.
        """
        storePath = filepath.FilePath(self.mktemp())
        st = store.Store(storePath)
        itemID = itemtest.PlainItem(store=st, plain=u'Hello, world!!!').storeID
        st.close()

        e = os.environ.copy()
        # Kind of a heuristic - hmmm
        e['PYTHONPATH'] = os.pathsep.join(sys.path) # os.pathsep.join([dir for dir in sys.path if not dir.startswith(sys.prefix)])
        d = defer.Deferred()
        p = ProcessOutputCollector(d)
        try:
            reactor.spawnProcess(p, sys.executable, ["python", '-Wignore', itemtestmain.__file__.rstrip('co'), storePath.path, str(itemID)], e)
        except NotImplementedError:
            raise unittest.SkipTest("Implement processes here")

        def cbOutput(output):
            self.assertEquals(''.join(output).strip(), 'Hello, world!!!')

        def ebBlah(err):
            log.err(err)
            self.fail(''.join(err.value.args[0].error))

        return d.addCallbacks(cbOutput, ebBlah)

    def testDeleteCreatePair(self):
        # Test coverage for a bug which was present in Axiom: deleting
        # the newest item in a database and then creating a new item
        # re-used the deleted item's oid causing all manner of
        # ridiculuousness.
        st = store.Store()

        i = itemtest.PlainItem(store=st)

        oldStoreID = i.storeID
        i.deleteFromStore()
        j = itemtest.PlainItem(store=st)
        self.failIfEqual(oldStoreID, j.storeID)

    def testDeleteThenLoad(self):
        st = store.Store()
        i = itemtest.PlainItem(store=st)
        oldStoreID = i.storeID
        self.assertEquals(st.getItemByID(oldStoreID, default=1234),
                          i)
        i.deleteFromStore()
        self.assertEquals(st.getItemByID(oldStoreID+100, default=1234),
                          1234)
        self.assertEquals(st.getItemByID(oldStoreID, default=1234),
                          1234)


    def test_duplicateDefinition(self):
        """
        When the same typeName is defined as an item class multiple times in
        memory, the second definition fails with a L{RuntimeError}.
        """
        class X(Item):
            dummy = integer()
        try:
            class X(Item):
                dummy = integer()
        except RuntimeError:
            pass
        else:
            self.fail("Duplicate definition should have failed.")


    def test_nonConflictingRedefinition(self):
        """
        If the python item class associated with a typeName is garbage
        collected, a new python item class can re-use that type name.
        """
        class X(Item):
            dummy = integer()
        del X
        class X(Item):
            dummy = integer()



class TestItem(Item):
    """
    Boring, behaviorless Item subclass used when we just need an item
    someplace.
    """
    attribute = integer()



class BrokenCommittedItem(Item):
    """
    Item class which changes database state in its committed method.  Don't
    write items like this, they're broken.
    """
    attribute = integer()
    _committed = inmemory()

    def committed(self):
        Item.committed(self)
        if getattr(self, '_committed', None) is not None:
            self._committed(self)



class CheckpointTestCase(TestCase):
    """
    Tests for Item checkpointing.
    """
    def setUp(self):
        self.checkpointed = []
        def checkpoint(item):
            self.checkpointed.append(item)
        self.originalCheckpoint = TestItem.checkpoint.im_func
        TestItem.checkpoint = checkpoint


    def tearDown(self):
        TestItem.checkpoint = self.originalCheckpoint


    def _autocommitBrokenCommittedMethodTest(self, method):
        store = Store()
        item = BrokenCommittedItem(store=store)
        item._committed = method
        self.assertRaises(ChangeRejected, setattr, item, 'attribute', 0)


    def _transactionBrokenCommittedMethodTest(self, method):
        store = Store()
        item = BrokenCommittedItem(store=store)
        item._committed = method

        def txn():
            item.attribute = 0
        self.assertRaises(ChangeRejected, store.transact, txn)


    def test_autocommitBrokenCommittedMethodMutate(self):
        """
        Test changing a persistent attribute in the committed (even if the
        original change was made in autocommit mode) callback raises
        L{ChangeRejected}.
        """
        def mutate(self):
            self.attribute = 0
        return self._autocommitBrokenCommittedMethodTest(mutate)


    def test_transactionBrokenCommittedMethodMutate(self):
        """
        Test changing a persistent attribute in the committed callback raises
        L{ChangeRejected}.
        """
        def mutate(item):
            item.attribute = 0
        return self._transactionBrokenCommittedMethodTest(mutate)


    def test_autocommitBrokenCommittedMethodDelete(self):
        """
        Test deleting an item in the committed (even if the original change was
        made in autocommit mode) callback raises L{ChangeRejected}.
        """
        def delete(item):
            item.deleteFromStore()
        return self._autocommitBrokenCommittedMethodTest(delete)


    def test_transactionBrokenCommittedMethodDelete(self):
        """
        Test changing a persistent attribute in the committed callback raises
        L{ChangeRejected}.
        """
        def delete(item):
            item.deleteFromStore()
        return self._transactionBrokenCommittedMethodTest(delete)


    def test_autocommitBrokenCommittedMethodCreate(self):
        """
        Test that creating a new item in a committed (even if the original
        change was made in autocommit mode) callback raises L{ChangeRejected}
        """
        def create(item):
            TestItem(store=item.store)
        return self._autocommitBrokenCommittedMethodTest(create)


    def test_transactionBrokenCommittedMethodCreate(self):
        """
        Test that creating a new item in a committed callback raises
        L{ChangeRejected}.
        """
        def create(item):
            TestItem(store=item.store)
        return self._transactionBrokenCommittedMethodTest(create)


    def test_autocommitCheckpoint(self):
        """
        Test that an Item is checkpointed when it is created outside of a
        transaction.
        """
        store = Store()
        item = TestItem(store=store)
        self.assertEquals(self.checkpointed, [item])


    def test_transactionCheckpoint(self):
        """
        Test that an Item is checkpointed when the transaction it is created
        within is committed.
        """
        store = Store()
        def txn():
            item = TestItem(store=store)
            self.assertEquals(self.checkpointed, [])
            return item
        item = store.transact(txn)
        self.assertEquals(self.checkpointed, [item])


    def test_queryCheckpoint(self):
        """
        Test that a newly created Item is checkpointed before a query is
        executed.
        """
        store = Store()
        def txn():
            item = TestItem(store=store)
            list(store.query(TestItem))
            self.assertEquals(self.checkpointed, [item])
        store.transact(txn)


    def test_autocommitTouchCheckpoint(self):
        """
        Test that an existing Item is checkpointed if it has an attribute
        changed on it.
        """
        store = Store()
        item = TestItem(store=store)

        # Get rid of the entry that's there from creation
        self.checkpointed = []

        item.attribute = 0
        self.assertEquals(self.checkpointed, [item])


    def test_transactionTouchCheckpoint(self):
        """
        Test that in a transaction an existing Item is checkpointed if it has
        touch called on it and the store it is in is checkpointed.
        """
        store = Store()
        item = TestItem(store=store)

        # Get rid of the entry that's there from creation
        self.checkpointed = []

        def txn():
            item.touch()
            store.checkpoint()
            self.assertEquals(self.checkpointed, [item])
        store.transact(txn)


    def test_twoQueriesOneCheckpoint(self):
        """
        Test that if two queries are performed in a transaction, a touched item
        only has checkpoint called on it before the first.
        """
        store = Store()
        item = TestItem(store=store)

        # Get rid of the entry that's there from creation
        self.checkpointed = []

        def txn():
            item.touch()
            list(store.query(TestItem))
            self.assertEquals(self.checkpointed, [item])
            list(store.query(TestItem))
            self.assertEquals(self.checkpointed, [item])
        store.transact(txn)
