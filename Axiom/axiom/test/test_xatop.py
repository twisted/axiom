
from twisted.trial import unittest

from epsilon import extime
from axiom import attributes, item, store, errors

class StoreTests(unittest.TestCase):
    def testCreation(self):
        dbdir = self.mktemp()
        s = store.Store(dbdir)
        s.close()

    def testReCreation(self):
        dbdir = self.mktemp()
        s = store.Store(dbdir)
        s.close()
        s = store.Store(dbdir)
        s.close()

class RevertException(Exception):
    pass


class TestItem(item.Item):
    schemaVersion = 1
    typeName = 'TestItem'
    foo = attributes.integer(indexed=True)
    bar = attributes.text()
    baz = attributes.timestamp()
    other = attributes.reference()

    activated = attributes.inmemory()
    checkactive = attributes.inmemory()
    checked = attributes.inmemory()

    def activate(self):
        self.activated = True
        if getattr(self, 'checkactive', False):
            assert isinstance(self.other, TestItem), repr(self.other)
            assert self.other != self, repr(self.other)
            self.checked = True


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
        self.dbdir = self.mktemp()
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
            baz = timeval
            )

        s.store = self.store
        sid = s.storeID
        self.store.close()
        self.store = store.Store(self.dbdir)
        s2 = self.store.getItemByID(sid)
        self.assertEquals(s2.foo, s.foo)

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

