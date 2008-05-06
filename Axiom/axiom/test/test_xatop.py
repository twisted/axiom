import sys
import os

from twisted.trial import unittest
from twisted.internet import protocol, defer
from twisted.python.util import sibpath
from twisted.python import filepath

from epsilon import extime
from axiom import attributes, item, store, errors

from pysqlite2.dbapi2 import sqlite_version_info


class RevertException(Exception):
    pass


class TestItem(item.Item):
    schemaVersion = 1
    typeName = 'TestItem'
    foo = attributes.integer(indexed=True, default=10)
    bar = attributes.text()
    baz = attributes.timestamp()
    other = attributes.reference()
    booleanT = attributes.boolean()
    booleanF = attributes.boolean()

    activated = attributes.inmemory()
    checkactive = attributes.inmemory()
    checked = attributes.inmemory()

    myStore = attributes.reference()

    attributes.compoundIndex(bar, baz)

    def activate(self):
        self.activated = True
        if getattr(self, 'checkactive', False):
            assert isinstance(self.other, TestItem), repr(self.other)
            assert self.other != self, repr(self.other)
            self.checked = True



class StoreTests(unittest.TestCase):
    def testCreation(self):
        dbdir = filepath.FilePath(self.mktemp())
        s = store.Store(dbdir)
        s.close()


    def testReCreation(self):
        dbdir = filepath.FilePath(self.mktemp())
        s = store.Store(dbdir)
        s.close()
        s = store.Store(dbdir)
        s.close()


    def test_onlyOneDir(self):
        """
        A Store should raise an error if both dbdir and filesdir are specified.
        """
        self.assertRaises(ValueError, store.Store,
                          filepath.FilePath(self.mktemp()), filesdir=filepath.FilePath(self.mktemp()))


    def testTableQueryCaching(self):
        """
        Ensure that the identity of the string returned by the
        mostly-private getTableQuery method is the same when it is invoked
        for the same type and version, rather than a newly constructed
        string.
        """
        s = store.Store()
        self.assertIdentical(
            s.getTableQuery(TestItem.typeName, 1),
            s.getTableQuery(TestItem.typeName, 1))


    def testTypeToDatabaseNames(self):
        # The real purpose of this test is to have the new get*Name
        # methods explicitely called somewhere in the test suite. The
        # effect itself does not actually matter much. These functions
        # are proven right by the fact that item creation, querying
        # and update are working.

        # I think the following should be ok for anything that vaguely
        # ressembles SQL.

        s = store.Store()
        tn = s.getTableName(TestItem)

        assert tn.startswith(s.databaseName)

        cn = s.getColumnName(TestItem.foo)
        scn = s.getShortColumnName(TestItem.foo)

        assert len(tn) < len(cn)
        assert len(scn) < len(cn)
        assert cn.endswith(scn)
        assert cn.startswith(tn)

        icn = s.getColumnName(TestItem.storeID)
        sicn = s.getShortColumnName(TestItem.storeID)

        assert len(tn) < len(icn)
        assert len(sicn) < len(icn)
        assert icn.endswith(sicn)
        assert icn.startswith(tn)

    def testGetTableName(self):
        """
        Item instances were getting into the table name cache.
        Make sure only classes are accepted.
        """
        s = store.Store()
        self.assertRaises(errors.ItemClassesOnly, s.getTableName, TestItem(store=s))

    def testTableNameCacheDoesntGrow(self):
        """
        Make sure the table name cache doesn't grow out of control anymore.
        """
        s = store.Store()
        tn = s.getTableName(TestItem)
        x = len(s.typeToTableNameCache)
        for i in range(10):
            s.getTableName(TestItem)
        self.assertEquals(x, len(s.typeToTableNameCache))
    def testStoreIDComparerIdentity(self):
        # We really want this to hold, because the storeID object is
        # used like a regular attribute as a key for various caching
        # within store.
        a0 = TestItem.storeID
        a1 = TestItem.storeID
        assert a0 is a1


class FailurePathTests(unittest.TestCase):

    def testNoCrossStoreRefs(self):
        s1 = store.Store()
        s2 = store.Store()

        t1 = TestItem(store=s1)
        self.assertRaises(errors.NoCrossStoreReferences,
                          TestItem, store=s2, other=t1)

        t2 = TestItem(store=s2)

        self.assertRaises(errors.NoCrossStoreReferences,
                          setattr, t2, 'other', t1)

        self.assertRaises(errors.NoCrossStoreReferences,
                          setattr, t2, 'other', s1)

        t3 = TestItem(other=t1)

        self.assertRaises(errors.NoCrossStoreReferences,
                          setattr, t3, 'store', s2)

        t3.store = s1

        self.assertEquals(list(s1.query(TestItem)),
                          [t1, t3])


class ItemTests(unittest.TestCase):
    def setUp(self):
        self.dbdir = filepath.FilePath(self.mktemp())
        self.store = store.Store(self.dbdir)

    def tearDown(self):
        self.store.close()

    def testFirstActivationHappensWhenAttributesAreSet(self):
        tio = TestItem(store=self.store)
        ti = TestItem(store=self.store,
                      checkactive=True,
                      other=tio)

        self.assertEquals(ti.checked, True)

    def testItemCreation(self):
        timeval = extime.Time.fromISO8601TimeAndDate('2004-10-05T10:12:14.1234')

        s = TestItem(
            foo = 42,
            bar = u'hello world',
            baz = timeval,
            booleanT = True,
            booleanF = False
            )
        s.myStore = self.store

        s.store = self.store
        sid = s.storeID
        self.store.close()
        self.store = store.Store(self.dbdir)
        s2 = self.store.getItemByID(sid)
        self.assertEquals(s2.foo, s.foo)
        self.assertEquals(s2.booleanT, s.booleanT)
        self.assertEquals(s2.booleanF, s.booleanF)
        self.assertIdentical(s2.myStore, self.store)


    def testBasicQuery(self):
        def tt():
            # !@#$ 3x+ speedup over not doing this in a transact()
            created = [TestItem(foo=x, bar=u"string-value-of-"+str(x))
                       for x in range(20)]
            for c in created:
                c.store = self.store

        self.store.transact(tt)

        loaded = self.store.query(TestItem,
                                  TestItem.foo >= 10)

        self.assertEquals(len(list(loaded)), 10)

    def testCreateThenDelete(self):
        timeval = extime.Time.fromISO8601TimeAndDate('2004-10-05T10:12:14.1234')
        sid = []
        def txn():
            s = TestItem(
                store = self.store,
                foo = 42,
                bar = u'hello world',
                baz = timeval,
                booleanT = True,
                booleanF = False
            )
            sid.append(s.storeID)
            self.assertEquals(list(self.store.query(TestItem)), [s])
            s.deleteFromStore()
            self.assertEquals(list(self.store.query(TestItem)), [])
            # hmm.  possibly due its own test.
            # self.assertRaises(KeyError, self.store.getItemByID, sid[0])

        self.store.transact(txn)
        self.assertRaises(KeyError, self.store.getItemByID, sid[0])
        self.assertEquals(list(self.store.query(TestItem)), [])


    def test_getNeverInsertedItem(self):
        """
        Verify that using getItemByID with a default object to attempt to
        load by storeID an Item which was created and deleted within a
        single transaction results in the default object.
        """
        def txn():
            a = TestItem(store=self.store)
            storeID = a.storeID
            a.deleteFromStore()
            del a
            return storeID
        storeID = self.store.transact(txn)
        default = object()
        result = self.store.getItemByID(storeID, default=default)
        self.assertIdentical(result, default)


    def testInMemoryRevert(self):
        item1 = TestItem(
            store=self.store,
            foo=24,
            bar=u'Zoom',
            baz=extime.Time.fromISO8601TimeAndDate('2004-10-05T10:12:14.1234')
            )

        def brokenFunction():
            item2 = TestItem(
                store=self.store,
                foo=42,
                bar=u'mooZ',
                baz=extime.Time.fromISO8601TimeAndDate('1970-03-12T05:05:11.5921')
                )

            item1.foo = 823
            item1.bar = u'this is the wrong answer'
            item1.baz = extime.Time()

            raise RevertException(item2.storeID)

        try:
            self.store.transact(brokenFunction)
        except RevertException, exc:
            [storeID] = exc.args

            self.assertRaises(KeyError, self.store.getItemByID, storeID)
            self.assertEquals(item1.foo, 24)
            self.assertEquals(item1.bar, u'Zoom')
            self.assertEquals(item1.baz.asISO8601TimeAndDate(), '2004-10-05T10:12:14.1234+00:00')
        else:
            self.fail("Transaction should have raised an exception")


class AttributefulItem(item.Item):
    schemaVersion = 1
    typeName = 'test_attributeful_item'

    withDefault = attributes.integer(default=42)
    withoutDefault = attributes.integer()

    def __repr__(self):
        return 'AttributeItem(oid=%s,withDefault=%s,withoutDefault=%s)'%  (
            self.storeID, self.withDefault, self.withoutDefault)

class StricterItem(item.Item):
    schemaVersion = 1
    typeName = 'test_stricter_item'

    aRef = attributes.reference(allowNone=False)


class AttributeTests(unittest.TestCase):
    def testGetAttribute(self):
        s = store.Store()
        def testGetAttribute():
            x = AttributefulItem(store=s)
            y = AttributefulItem(store=s, withDefault=20)
            z = AttributefulItem(store=s, withoutDefault=30)
            for o in x, y, z:
                o.checkpoint()

            self.assertEquals(x.withDefault, 42)
            self.assertEquals(x.withoutDefault, None)
            self.assertEquals(y.withDefault, 20)
            self.assertEquals(y.withoutDefault, None)
            self.assertEquals(z.withDefault, 42)
            self.assertEquals(z.withoutDefault, 30)
        s.transact(testGetAttribute)

    def testIntegerAttribute_SQLiteBug(self):
        # SQLite 3.2.1 has a bug which causes various integers to be stored
        # incorrect.  For example, 2 ** 48 - 1 is stored as -1.  This is
        # fixed in 3.2.7.

        for power in 8, 16, 24, 32, 48, 63:
            s = store.Store()
            input = 2 ** power - 1
            s.transact(
                AttributefulItem,
                store=s,
                withoutDefault=input)
            output = s.findFirst(AttributefulItem).withoutDefault
            self.assertEquals(input, output)
            s.close()

    if sqlite_version_info < (3, 2, '7'):
        testIntegerAttribute_SQLiteBug.todo = (
            "If this test fails on your system, you should really upgrade SQLite "
            "to at least 3.2.7.  Not doing so will lead to corruption of your "
            "data.")

    def testQueries(self):
        s = store.Store()
        def testQueries():
            x = AttributefulItem(store=s, withDefault=50)
            y = AttributefulItem(store=s, withDefault=30)
            z = AttributefulItem(store=s, withoutDefault=30)

            for o in x, y, z:
                o.checkpoint()

            self.assertEquals(
                list(s.query(AttributefulItem, AttributefulItem.withoutDefault != None,
                             sort=AttributefulItem.withoutDefault.desc)),
                [z])

            self.assertEquals(
                list(s.query(AttributefulItem, sort=AttributefulItem.withDefault.desc)),
                [x, z, y])

        s.transact(testQueries)

    def testDontAllowNone(self):
        s = store.Store()
        def testDontAllowNone():
            try:
                x = StricterItem(store=s)
            except TypeError:
                pass
            else:
                self.fail("Creating a StricterItem without an aRef value should have failed")

            a = AttributefulItem(store=s)
            x = StricterItem(store=s, aRef=a)
            self.assertEquals(x.aRef, a)

            try:
                x.aRef = None
            except TypeError:
                pass
            else:
                self.fail("Setting aRef to None on a StricterItem should have failed")
        s.transact(testDontAllowNone)


class TestFindOrCreate(unittest.TestCase):

    def testCreate(self):
        s = store.Store()
        ai = s.findOrCreate(AttributefulItem)
        self.assertEquals(ai.withDefault, 42)
        self.assertEquals(ai.withoutDefault, None)

    def testFind(self):
        s = store.Store()
        ai = s.findOrCreate(AttributefulItem, withoutDefault=1234)
        ai2 = s.findOrCreate(AttributefulItem, withDefault=42)
        ai3 = s.findOrCreate(AttributefulItem)

        ai4 = s.findOrCreate(AttributefulItem, withDefault=71)
        ai5 = s.findOrCreate(AttributefulItem, withDefault=71)

        self.assertIdentical(ai, ai2)
        self.assertIdentical(ai3, ai2)
        self.assertIdentical(ai4, ai5)
        self.assertNotIdentical(ai, ai4)

    def testIfNew(self):
        l = []
        s = store.Store()

        ai1 = s.findOrCreate(AttributefulItem, l.append, withDefault=1234)
        ai2 = s.findOrCreate(AttributefulItem, l.append, withDefault=1234)
        ai3 = s.findOrCreate(AttributefulItem, l.append, withDefault=4321)
        ai4 = s.findOrCreate(AttributefulItem, l.append, withDefault=4321)

        self.assertEquals(len(l), 2)
        self.assertEquals(l, [ai1, ai3])

    def testFindFirst(self):
        s = store.Store()
        a0 = ai = AttributefulItem(store=s)
        ai2 = s.findFirst(AttributefulItem, AttributefulItem.withDefault == 42)
        shouldBeNone = s.findFirst(AttributefulItem, AttributefulItem.withDefault == 99)
        self.assertEquals(ai, ai2)
        self.assertEquals(shouldBeNone, None)

        ai = AttributefulItem(store=s, withDefault=24)
        ai2 = s.findFirst(AttributefulItem, AttributefulItem.withDefault == 24)
        self.assertEquals(ai, ai2)

        ai = AttributefulItem(store=s, withDefault=55)
        ai2 = s.findFirst(AttributefulItem)
        self.assertEquals(a0, ai2)



class DeletedTrackingItem(item.Item):
    """
    Helper class for testing that C{deleted} is called by
    ItemQuery.deleteFromStore.
    """
    deletedTimes = 0
    value = attributes.integer()

    def deleted(self):
        DeletedTrackingItem.deletedTimes += 1



class DeleteFromStoreTrackingItem(item.Item):
    """
    Helper class for testing that C{deleteFromStore} is called by
    ItemQuery.deleteFromStore.
    """
    deletedTimes = 0
    value = attributes.integer()

    def deleteFromStore(self):
        DeleteFromStoreTrackingItem.deletedTimes += 1
        item.Item.deleteFromStore(self)



class MassInsertDeleteTests(unittest.TestCase):

    def setUp(self):
        self.storepath = filepath.FilePath(self.mktemp())
        self.store = store.Store(self.storepath)

    def testBatchInsert(self):
        """
        Make sure that batchInsert creates all the items it's supposed
        to with appropriate attributes.
        """

        dataRows = [(37, 93),
                    (1,   2)]

        self.store.batchInsert(AttributefulItem,
                              [AttributefulItem.withDefault,
                               AttributefulItem.withoutDefault],
                              dataRows)
        items = list(self.store.query(AttributefulItem))
        self.assertEquals(items[0].withDefault, 37)
        self.assertEquals(items[0].withoutDefault, 93)
        self.assertEquals(items[1].withDefault, 1)
        self.assertEquals(items[1].withoutDefault, 2)

    def testTransactedBatchInsert(self):
        """
        Test that batchInsert works in a transaction.
        """
        dataRows = [(37, 93),
                    (1,   2)]

        self.store.transact(self.store.batchInsert,
                            AttributefulItem,
                            [AttributefulItem.withDefault,
                             AttributefulItem.withoutDefault],
                            dataRows)

        items = list(self.store.query(AttributefulItem))
        self.assertEquals(items[0].withDefault, 37)
        self.assertEquals(items[0].withoutDefault, 93)
        self.assertEquals(items[1].withDefault, 1)
        self.assertEquals(items[1].withoutDefault, 2)

    def testBatchInsertReference(self):
        """
        Test that reference args are handled okay by batchInsert.
        """
        itemA = AttributefulItem(store=self.store)
        itemB = AttributefulItem(store=self.store)
        dataRows = [(1, u"hello", extime.Time(),
                     itemA, True, False, self.store),
                    (2, u"hoorj", extime.Time(),
                     itemB, False, True, self.store)]

        self.store.batchInsert(TestItem,
                               [TestItem.foo, TestItem.bar,
                                TestItem.baz, TestItem.other,
                                TestItem.booleanT, TestItem.booleanF,
                                TestItem.myStore],
                               dataRows)
        items = list(self.store.query(TestItem))

        self.assertEquals(items[0].other, itemA)
        self.assertEquals(items[1].other, itemB)
        self.assertEquals(items[0].store, self.store)
        self.assertEquals(items[1].store, self.store)

    def testMemoryBatchInsert(self):
        """
        Test that batchInsert works on an in-memory store.
        """
        self.store = store.Store()
        self.testBatchInsert()

    def testBatchInsertSelectedAttributes(self):
        """
        Test that batchInsert does the right thing when only a few
        attributes are being set.
        """
        dataRows = [(u"hello", 50, False, self.store),
                    (u"hoorj", None, True, self.store)]

        self.store.batchInsert(TestItem,
                               [TestItem.bar,
                                TestItem.foo,
                                TestItem.booleanF,
                                TestItem.myStore],
                               dataRows)
        items = list(self.store.query(TestItem))

        self.assertEquals(items[0].other, None)
        self.assertEquals(items[1].other, None)
        self.assertEquals(items[0].foo, 50)
        self.assertEquals(items[1].foo, None)
        self.assertEquals(items[0].bar, u"hello")
        self.assertEquals(items[1].bar, u"hoorj")
        self.assertEquals(items[0].store, self.store)
        self.assertEquals(items[1].store, self.store)

    def testBatchDelete(self):
        """
        Ensure that unqualified batchDelete removes all the items of a
        certain class.
        """
        for i in xrange(10):
            AttributefulItem(store=self.store, withoutDefault=i)

        self.store.query(AttributefulItem).deleteFromStore()
        self.assertEquals(list(self.store.query(AttributefulItem)), [])

    def testBatchDeleteCondition(self):
        """
        Ensure that conditions for batchDelete are honored properly.
        """
        for i in xrange(10):
            AttributefulItem(store=self.store, withoutDefault=i)

        self.store.query(AttributefulItem,
                              AttributefulItem.withoutDefault > 4
                         ).deleteFromStore()
        self.assertEquals(self.store.query(AttributefulItem).count(), 5)

    def testSlowBatchDelete(self):
        """
        Ensure that a 'deleted' method on an Item will be called if it exists.
        """
        DeletedTrackingItem(store=self.store)
        self.store.query(DeletedTrackingItem).deleteFromStore()
        self.assertEqual(DeletedTrackingItem.deletedTimes, 1)


    def test_slowBatchDeleteBecauseDeletedFromStore(self):
        """
        Ensure that a 'deleteFromStore' method on an Item will be called if it
        exists.
        """
        DeleteFromStoreTrackingItem(store=self.store)
        self.store.query(DeleteFromStoreTrackingItem).deleteFromStore()
        self.assertEqual(DeleteFromStoreTrackingItem.deletedTimes, 1)


# Item types we will use to change the underlying database schema (by creating
# them).
class ConcurrentItemA(item.Item):
    anAttribute = attributes.text()

class ConcurrentItemB(item.Item):
    anotherAttribute = attributes.integer()

class ProcessConcurrencyTestCase(unittest.TestCase,
                                 protocol.ProcessProtocol):

    def spawn(self, *args):
        self.d = defer.Deferred()
        from twisted.internet import reactor
        reactor.spawnProcess(
            self,
            sys.executable,
            [sys.executable] + list(args),
            os.environ)
        return self.d

    ok = 0

    def outReceived(self, data):
        if data == '1':
            # step 1: create an item
            cia = ConcurrentItemA(store=self.store,
                                  anAttribute=u'aaa')
            # then tell the subprocess to load it
            self.transport.write(str(cia.storeID)+'\n')
        elif data == '2':
            # step 2: the subprocess has notified us that it has successfully
            # completed
            self.ok = 1

    def errReceived(self, data):
        # we should never *really* get anything to stdout
        print data

    def processEnded(self, reason):
        # total correctness would have us checking the exit code too, but we
        # got all the output we expected, so whatever.
        if self.ok:
            self.d.callback('OK')
        else:
            self.d.errback(reason)

    def testNewItemTypeInSubprocess(self):
        dbdir = filepath.FilePath(self.mktemp())
        self.store = store.Store(dbdir)
        # Open the store and leave its schema empty (don't create any items)
        # until the subprocess has opened it and loaded the bogus schema.
        return self.spawn(sibpath(__file__, "openthenload.py"), dbdir.path)


class ConcurrencyTestCase(unittest.TestCase):
    def testSchemaChange(self):
        """
        When a statement is executed after the underlying schema has been
        changed (tables are added, database is vacuumed, etc) by another thread
        of execution, PySQLite2 will raise an OperationalError.  This is
        basically harmless and the query will work if re-executed.  This should
        be done transparently.
        """
        dbdir = filepath.FilePath(self.mktemp())

        firstStore = store.Store(dbdir)
        ConcurrentItemA(store=firstStore)

        secondStore = store.Store(dbdir)

        self.assertNotIdentical(firstStore, secondStore) # if this line starts
                                                         # breaking, rewrite
                                                         # this test.

        ConcurrentItemB(store=firstStore)

        self.assertEquals(secondStore.query(ConcurrentItemA).count(), 1)


    def testNewItemType(self):
        """
        Creating the first instance of a of an Item subclass changes the
        underlying database schema as well as some Store-private state which
        tracks that schema.  Test to make sure that creating the first instance
        of an Item subclass in one store is reflected in a second store.
        """
        dbdir = filepath.FilePath(self.mktemp())

        firstStore = store.Store(dbdir)
        secondStore = store.Store(dbdir)

        ConcurrentItemA(store=firstStore)
        self.assertEquals(secondStore.query(ConcurrentItemA).count(), 1)
