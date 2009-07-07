
from twisted.trial import unittest
from twisted.python import failure, filepath
from twisted.application import service

from axiom import iaxiom, store, item, attributes, batch, substore

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
        self.scheduler = iaxiom.IScheduler(self.store)


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

        # Make some work, step the processor, and fake the error handling
        # behavior the Scheduler actually provides.
        for i in range(3):
            TestWorkUnit(store=self.store, information=i)
            try:
                proc.step()
            except batch._ProcessingFailure:
                proc.timedEventErrorHandler(
                    (u"Oh crap, I do not have a TimedEvent, "
                     "I sure hope that never becomes a problem."),
                    failure.Failure())

        self.assertEquals(processedItems, [0, 2])

        errors = list(proc.getFailedItems())
        self.assertEquals(len(errors), 1)
        self.assertEquals(errors[0][0], listener)
        self.assertEquals(errors[0][1].information, 1)

        loggedErrors = self.flushLoggedErrors(RuntimeError)
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


    def testSuperfluousItemAddition(self):
        """
        Test the addItem method for work which would have been done already,
        and so for which addItem should therefore be a no-op.
        """
        processedItems = []
        def listener(item):
            processedItems.append(item.information)

        proc = self.procType(store=self.store)
        listener = WorkListener(store=self.store, listener=listener)

        # Create a couple items so there will be backwards work to do.
        one = TestWorkUnit(store=self.store, information=0)
        two = TestWorkUnit(store=self.store, information=1)

        rellist = proc.addReliableListener(listener)

        # Create a couple more items so there will be some forwards work to do.
        three = TestWorkUnit(store=self.store, information=2)
        four = TestWorkUnit(store=self.store, information=3)

        # There are only two regions at this point - work behind and work
        # ahead; no work has been done yet, so there's no region in between.
        # Add items behind and ahead of the point; these should not result in
        # any explicit tracking items, since they would have been processed in
        # due course anyway.
        rellist.addItem(two)
        rellist.addItem(three)

        for i in range(100):
            if not proc.step():
                break
        else:
            self.fail("Processing loop took too long")

        self.assertEquals(processedItems, [2, 3, 1, 0])


    def testReprocessItemAddition(self):
        """
        Test the addItem method for work which is within the bounds of work
        already done, and so which would not have been processed without the
        addItem call.
        """
        processedItems = []
        def listener(item):
            processedItems.append(item.information)

        proc = self.procType(store=self.store)
        listener = WorkListener(store=self.store, listener=listener)
        rellist = proc.addReliableListener(listener)

        one = TestWorkUnit(store=self.store, information=0)
        two = TestWorkUnit(store=self.store, information=1)
        three = TestWorkUnit(store=self.store, information=2)

        for i in range(100):
            if not proc.step():
                break
        else:
            self.fail("Processing loop took too long")

        self.assertEquals(processedItems, range(3))

        # Now that we have processed some items, re-add one of those items to
        # be re-processed and make sure it actually does get passed to the
        # listener again.
        processedItems = []

        rellist.addItem(two)

        for i in xrange(100):
            if not proc.step():
                break
        else:
            self.fail("Processing loop took too long")

        self.assertEquals(processedItems, [1])


    def test_processorStartsUnscheduled(self):
        """
        Test that when a processor is first created, it is not scheduled to
        perform any work.
        """
        proc = self.procType(store=self.store)
        self.assertIdentical(proc.scheduled, None)
        self.assertEquals(
            list(self.scheduler.scheduledTimes(proc)),
            [])


    def test_itemAddedIgnoredWithoutListeners(self):
        """
        Test that if C{itemAdded} is called while the processor is idle but
        there are no listeners, the processor does not schedule itself to do
        any work.
        """
        proc = self.procType(store=self.store)
        proc.itemAdded()
        self.assertEqual(proc.scheduled, None)
        self.assertEquals(
            list(self.scheduler.scheduledTimes(proc)),
            [])


    def test_itemAddedSchedulesProcessor(self):
        """
        Test that if C{itemAdded} is called while the processor is idle and
        there are listeners, the processor does schedules itself to do some
        work.
        """
        proc = self.procType(store=self.store)
        listener = WorkListener(store=self.store)
        proc.addReliableListener(listener)

        # Get rid of the scheduler state that addReliableListener call just
        # created.
        proc.scheduled = None
        self.scheduler.unscheduleAll(proc)

        proc.itemAdded()
        self.failIfEqual(proc.scheduled, None)
        self.assertEquals(
            list(self.scheduler.scheduledTimes(proc)),
            [proc.scheduled])


    def test_addReliableListenerSchedulesProcessor(self):
        """
        Test that if C{addReliableListener} is called while the processor is
        idle, the processor schedules itself to do some work.
        """
        proc = self.procType(store=self.store)
        listener = WorkListener(store=self.store)
        proc.addReliableListener(listener)
        self.failIfEqual(proc.scheduled, None)
        self.assertEquals(
            list(self.scheduler.scheduledTimes(proc)),
            [proc.scheduled])


    def test_itemAddedWhileScheduled(self):
        """
        Test that if C{itemAdded} is called when the processor is already
        scheduled to run, the processor remains scheduled to run at the same
        time.
        """
        proc = self.procType(store=self.store)
        listener = WorkListener(store=self.store)
        proc.addReliableListener(listener)
        when = proc.scheduled
        proc.itemAdded()
        self.assertEquals(proc.scheduled, when)
        self.assertEquals(
            list(self.scheduler.scheduledTimes(proc)),
            [proc.scheduled])


    def test_addReliableListenerWhileScheduled(self):
        """
        Test that if C{addReliableListener} is called when the processor is
        already scheduled to run, the processor remains scheduled to run at the
        same time.
        """
        proc = self.procType(store=self.store)
        listenerA = WorkListener(store=self.store)
        proc.addReliableListener(listenerA)
        when = proc.scheduled
        listenerB = WorkListener(store=self.store)
        proc.addReliableListener(listenerB)
        self.assertEquals(proc.scheduled, when)
        self.assertEquals(
            list(self.scheduler.scheduledTimes(proc)),
            [proc.scheduled])


    def test_processorIdlesWhenCaughtUp(self):
        """
        Test that the C{run} method of the processor returns C{None} when it
        has done all the work it needs to do, thus unscheduling the processor.
        """
        proc = self.procType(store=self.store)
        self.assertIdentical(proc.run(), None)



class BatchCallTestItem(item.Item):
    called = attributes.boolean(default=False)

    def callIt(self):
        self.called = True



class BrokenException(Exception):
    """
    Exception always raised by L{BrokenReliableListener.processItem}.
    """



class BatchWorkItem(item.Item):
    """
    Item class which will be delivered as work units for testing error handling
    around reliable listeners.
    """
    value = attributes.text(default=u"unprocessed")



BatchWorkSource = batch.processor(BatchWorkItem)



class BrokenReliableListener(item.Item):
    """
    A listener for batch work which always raises an exception from its
    processItem method.  Used to test that errors from processItem are properly
    handled.
    """

    anAttribute = attributes.integer()

    def processItem(self, item):
        raise BrokenException("Broken Reliable Listener is working as expected.")



class WorkingReliableListener(item.Item):
    """
    A listener for batch work which actually works.  Used to test that even if
    a broken reliable listener is around, working ones continue to receive new
    items to process.
    """

    anAttribute = attributes.integer()

    def processItem(self, item):
        item.value = u"processed"



class RemoteTestCase(unittest.TestCase):
    def testBatchService(self):
        """
        Make sure SubStores can be adapted to L{iaxiom.IBatchService}.
        """
        dbdir = filepath.FilePath(self.mktemp())
        s = store.Store(dbdir)
        ss = substore.SubStore.createNew(s, 'substore')
        bs = iaxiom.IBatchService(ss)
        self.failUnless(iaxiom.IBatchService.providedBy(bs))


    def testProcessLifetime(self):
        """
        Test that the batch system process can be started and stopped.
        """
        dbdir = filepath.FilePath(self.mktemp())
        s = store.Store(dbdir)
        svc = batch.BatchProcessingControllerService(s)
        svc.startService()
        return svc.stopService()


    def testCalling(self):
        """
        Test invoking a method on an item in the batch process.
        """
        dbdir = filepath.FilePath(self.mktemp())
        s = store.Store(dbdir)
        ss = substore.SubStore.createNew(s, 'substore')
        service.IService(s).startService()
        d = iaxiom.IBatchService(ss).call(BatchCallTestItem(store=ss.open()).callIt)
        def called(ign):
            self.failUnless(ss.open().findUnique(BatchCallTestItem).called, "Was not called")
            return service.IService(s).stopService()
        return d.addCallback(called)


    def testProcessingServiceStepsOverErrors(self):
        """
        If any processor raises an unexpected exception, the work unit which
        was being processed should be marked as having had an error and
        processing should move on to the next item.  Make sure that this
        actually happens when L{BatchProcessingService} is handling those
        errors.
        """
        BATCH_WORK_UNITS = 3

        dbdir = filepath.FilePath(self.mktemp())
        st = store.Store(dbdir)
        source = BatchWorkSource(store=st)
        for i in range(BATCH_WORK_UNITS):
            BatchWorkItem(store=st)

        source.addReliableListener(BrokenReliableListener(store=st), iaxiom.REMOTE)
        source.addReliableListener(WorkingReliableListener(store=st), iaxiom.REMOTE)

        svc = batch.BatchProcessingService(st, iaxiom.REMOTE)

        task = svc.step()

        # Loop 6 (BATCH_WORK_UNITS * 2) times - three items times two
        # listeners, it should not take any more than six iterations to
        # completely process all work.
        for i in xrange(BATCH_WORK_UNITS * 2):
            task.next()


        self.assertEquals(
            len(self.flushLoggedErrors(BrokenException)),
            BATCH_WORK_UNITS)

        self.assertEquals(
            st.query(BatchWorkItem, BatchWorkItem.value == u"processed").count(),
            BATCH_WORK_UNITS)
