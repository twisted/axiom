
from twisted.trial import unittest
from twisted.python import log

from axiom import store, item, attributes, batch


class TestWorkUnit(item.Item):
    information = attributes.integer()

    def __repr__(self):
        return '<TestWorkUnit %d>' % (self.information,)


class ExtraUnit(item.Item):
    unformashun = attributes.text()



class WorkListener(item.Item):
    comply = attributes.integer(doc="""
    This exists solely to satisfy the requirement that Items have at
    least one persistent attribute.
    """)

    listener = attributes.inmemory(doc="""
    A callable which will be invoked by processItem.  This will be
    provided by the test method and will assert that the appropriate
    items are received, in the appropriate order.
    """)

    def processItem(self, item):
        self.listener(item)



class BatchTestCase(unittest.TestCase):
    def setUp(self):
        self.procType = batch.processor(TestWorkUnit)
        self.store = store.Store()


    def testItemTypeCreation(self):
        """
        Test that processors for a different Item types can be
        created, that they are valid Item types themselves, and that
        repeated calls return the same object when appropriate.
        """
        procB = batch.processor(TestWorkUnit)
        self.assertIdentical(self.procType, procB)

        procC = batch.processor(ExtraUnit)
        self.failIfIdentical(procB, procC)
        self.failIfEqual(procB.typeName, procC.typeName)


    def testInstantiation(self):
        """
        Test that a batch processor can be instantiated and added to a
        database, and that it can be retrieved in the usual ways.
        """
        proc = self.procType(store=self.store)
        self.assertIdentical(self.store.findUnique(self.procType), proc)


    def testListenerlessProcessor(self):
        """
        Test that a batch processor can be stepped even if it has no
        listeners, and that it correctly reports it has no work to do.
        """
        proc = self.procType(store=self.store)
        self.failIf(proc.step(), "expected no more work to be reported, some was")

        TestWorkUnit(store=self.store, information=0)
        self.failIf(proc.step(), "expected no more work to be reported, some was")


    def testListeners(self):
        """
        Test that items can register or unregister their interest in a
        processor's batch of items.
        """
        proc = self.procType(store=self.store)
        listenerA = WorkListener(store=self.store)
        listenerB = WorkListener(store=self.store)

        self.assertEquals(list(proc.getReliableListeners()), [])

        proc.addReliableListener(listenerA)
        self.assertEquals(list(proc.getReliableListeners()), [listenerA])

        proc.addReliableListener(listenerB)
        expected = [listenerA, listenerB]
        listeners = list(proc.getReliableListeners())
        self.assertEquals(sorted(expected), sorted(listeners))

        proc.removeReliableListener(listenerA)
        self.assertEquals(list(proc.getReliableListeners()), [listenerB])

        proc.removeReliableListener(listenerB)
        self.assertEquals(list(proc.getReliableListeners()), [])


    def testBasicProgress(self):
        """
        Test that when a processor is created and given a chance to
        run, it completes some work.
        """
        processedItems = []
        def listener(item):
            processedItems.append(item.information)

        proc = self.procType(store=self.store)
        listener = WorkListener(store=self.store, listener=listener)

        proc.addReliableListener(listener)

        self.assertEquals(processedItems, [])

        self.failIf(proc.step(), "expected no work to be reported, some was")

        self.assertEquals(processedItems, [])

        for i in range(3):
            TestWorkUnit(store=self.store, information=i)
            ExtraUnit(store=self.store, unformashun=unicode(-i))

        self.failUnless(proc.step(), "expected more work to be reported, none was")
        self.assertEquals(processedItems, [0])

        self.failUnless(proc.step(), "expected more work to be reported, none was")
        self.assertEquals(processedItems, [0, 1])

        self.failIf(proc.step(), "expected no more work to be reported, some was")
        self.assertEquals(processedItems, [0, 1, 2])

        self.failIf(proc.step(), "expected no more work to be reported, some was")
        self.assertEquals(processedItems, [0, 1, 2])


    def testProgressAgainstExisting(self):
        """
        Test that when a processor is created when work units exist
        already, it works backwards to notify its listener of all
        those existing work units.  Also test that work units created
        after the processor are also handled.
        """
        processedItems = []
        def listener(item):
            processedItems.append(item.information)

        proc = self.procType(store=self.store)
        listener = WorkListener(store=self.store, listener=listener)

        for i in range(3):
            TestWorkUnit(store=self.store, information=i)

        proc.addReliableListener(listener)

        self.assertEquals(processedItems, [])

        self.failUnless(proc.step(), "expected more work to be reported, none was")
        self.assertEquals(processedItems, [2])

        self.failUnless(proc.step(), "expected more work to be reported, none was")
        self.assertEquals(processedItems, [2, 1])

        self.failIf(proc.step(), "expected no more work to be reported, some was")
        self.assertEquals(processedItems, [2, 1, 0])

        self.failIf(proc.step(), "expected no more work to be reported, some was")
        self.assertEquals(processedItems, [2, 1, 0])

        for i in range(3, 6):
            TestWorkUnit(store=self.store, information=i)

        self.failUnless(proc.step(), "expected more work to be reported, none was")
        self.assertEquals(processedItems, [2, 1, 0, 3])

        self.failUnless(proc.step(), "expected more work to be reported, none was")
        self.assertEquals(processedItems, [2, 1, 0, 3, 4])

        self.failIf(proc.step(), "expected no more work to be reported, some was")
        self.assertEquals(processedItems, [2, 1, 0, 3, 4, 5])

        self.failIf(proc.step(), "expected no more work to be reported, some was")
        self.assertEquals(processedItems, [2, 1, 0, 3, 4, 5])


    def testBrokenListener(self):
        """
        Test that if a listener's processItem method raises an
        exception, processing continues beyond that item and that an
        error marker is created for that item.
        """

        errmsg = "This reliable listener is not very reliable!"
        processedItems = []
        def listener(item):
            if item.information == 1:
                raise RuntimeError(errmsg)
            processedItems.append(item.information)

        proc = self.procType(store=self.store)
        listener = WorkListener(store=self.store, listener=listener)

        proc.addReliableListener(listener)

        for i in range(3):
            TestWorkUnit(store=self.store, information=i)
            proc.step()

        self.assertEquals(processedItems, [0, 2])

        errors = list(proc.getFailedItems())
        self.assertEquals(len(errors), 1)
        self.assertEquals(errors[0][0], listener)
        self.assertEquals(errors[0][1].information, 1)

        loggedErrors = log.flushErrors(RuntimeError)
        self.assertEquals(len(loggedErrors), 1)
        self.assertEquals(loggedErrors[0].getErrorMessage(), errmsg)


    def testMultipleListeners(self):
        """
        Test that a single batch processor with multiple listeners
        added at different times delivers each item to each listener.
        """
        processedItemsA = []
        def listenerA(item):
            processedItemsA.append(item.information)

        processedItemsB = []
        def listenerB(item):
            processedItemsB.append(item.information)

        proc = self.procType(store=self.store)

        for i in range(2):
            TestWorkUnit(store=self.store, information=i)

        firstListener = WorkListener(store=self.store, listener=listenerA)
        proc.addReliableListener(firstListener)

        for i in range(2, 4):
            TestWorkUnit(store=self.store, information=i)

        secondListener = WorkListener(store=self.store, listener=listenerB)
        proc.addReliableListener(secondListener)

        for i in range(4, 6):
            TestWorkUnit(store=self.store, information=i)

        for i in range(100):
            if not proc.step():
                break
        else:
            self.fail("Processing loop took too long")

        self.assertEquals(
            processedItemsA, [2, 3, 4, 5, 1, 0])

        self.assertEquals(
            processedItemsB, [4, 5, 3, 2, 1, 0])


    def testRepeatedAddListener(self):
        """
        Test that adding the same listener repeatedly has the same
        effect as adding it once.
        """
        proc = self.procType(store=self.store)
        listener = WorkListener(store=self.store)
        proc.addReliableListener(listener)
        proc.addReliableListener(listener)
        self.assertEquals(list(proc.getReliableListeners()), [listener])
