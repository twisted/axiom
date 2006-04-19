
import sys, os

from twisted.trial import unittest
from twisted.internet import error, protocol, defer, reactor
from twisted.protocols import policies
from twisted.python import log

from axiom import store, item
from axiom.test import itemtest, itemtestmain

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

class TestItem(unittest.TestCase):
    def testCreateItem(self):
        st = store.Store()
        self.assertRaises(item.CantInstantiateItem, item.Item, store=st)


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
