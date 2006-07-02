
import sys, os

from twisted.trial import unittest
from twisted.internet import error, protocol, defer, reactor
from twisted.protocols import policies
from twisted.python import log

from axiom import store, item
from axiom.test import itemtest, itemtestmain
from axiom.attributes import text, inmemory

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



class TestItem(unittest.TestCase):
    def testCreateItem(self):
        st = store.Store()
        self.assertRaises(item.CantInstantiateItem, item.Item, store=st)


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
        storePath = self.mktemp()
        st = store.Store(storePath)
        itemID = itemtest.PlainItem(store=st, plain=u'Hello, world!!!').storeID
        st.close()

        e = os.environ.copy()
        # Kind of a heuristic - hmmm
        e['PYTHONPATH'] = os.pathsep.join(sys.path) # os.pathsep.join([dir for dir in sys.path if not dir.startswith(sys.prefix)])
        d = defer.Deferred()
        p = ProcessOutputCollector(d)
        try:
            reactor.spawnProcess(p, sys.executable, ["python", '-Wignore', itemtestmain.__file__.rstrip('co'), storePath, str(itemID)], e)
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
