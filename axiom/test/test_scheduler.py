# -*- test-case-name: axiom.test.test_scheduler -*-

import gc
from datetime import timedelta

from twisted.trial import unittest
from twisted.trial.unittest import TestCase
from twisted.application.service import IService
from twisted.internet.defer import Deferred
from twisted.internet.task import Clock
from twisted.python import filepath, versions

from epsilon.extime import Time

from axiom.scheduler import TimedEvent, _SubSchedulerParentHook, TimedEventFailureLog
from axiom.scheduler import Scheduler, SubScheduler
from axiom.store import Store
from axiom.item import Item
from axiom.substore import SubStore

from axiom.attributes import integer, text, inmemory, boolean, timestamp
from axiom.iaxiom import IScheduler
from axiom.dependency import installOn

class TestEvent(Item):

    typeName = 'test_event'
    schemaVersion = 1

    testCase = inmemory()       # this won't fall out of memory due to
                                # caching, thanks.
    name = text()

    runCount = integer()
    runAgain = integer()        # milliseconds to add, then run again
    winner = integer(default=0) # is this the event that is supposed to
                                # complete the test successfully?

    def __init__(self, **kw):
        super(TestEvent, self).__init__(**kw)
        self.runCount = 0

    def run(self):
        # When this is run from testSubScheduler, we want to make an
        # additional assertion.  There is exactly one SubStore in this
        # configuration, so there should be no more than one
        # TimedEvent with a _SubSchedulerParentHook as its runnable.
        if self.store.parent is not None:
            count = 0
            s = self.store.parent
            for evt in s.query(TimedEvent):
                if isinstance(evt.runnable, _SubSchedulerParentHook):
                    count += 1
            if count > 1:
                return self.fail("Too many TimedEvents for the SubStore: %d" % (count,))

        self.runCount += 1
        if self.runAgain is not None:
            result = self.testCase.now() + timedelta(seconds=self.runAgain)
            self.runAgain = None
        else:
            result = None
        return result

    def fail(self, msg):
        self.testCase.fail(msg)


class NotActuallyRunnable(Item):
    huhWhat = integer()

class SpecialError(Exception):
    pass

class SpecialErrorHandler(Item):
    huhWhat = integer()
    broken = integer(default=0)
    procd = integer(default=0)

    def run(self):
        self.broken = 1
        raise SpecialError()

    def timedEventErrorHandler(self, timedEvent, failureObj):
        failureObj.trap(SpecialError)
        self.procd = 1



class HookRunner(Item):
    """
    Runnable that simply calls a supplied hook.
    """
    ignored = integer()
    hook = inmemory()

    def run(self):
        self.hook(self)



class SchedTest:
    def tearDown(self):
        return IService(self.siteStore).stopService()


    def setUp(self):
        self.clock = Clock()

        scheduler = IScheduler(self.siteStore)
        self.stubTime(scheduler)
        IService(self.siteStore).startService()


    def now(self):
        return Time.fromPOSIXTimestamp(self.clock.seconds())


    def stubTime(self, scheduler):
        scheduler.callLater = self.clock.callLater
        scheduler.now = self.now


    def test_implementsSchedulerInterface(self):
        """
        Verify that IScheduler is declared as implemented.
        """
        self.failUnless(IScheduler.providedBy(IScheduler(self.store)))


    def test_scheduler(self):
        """
        Test that the ordering and timing of scheduled calls is correct.
        """
        # create 3 timed events.  the first one fires.  the second one fires,
        # then reschedules itself.  the third one should never fire because the
        # reactor is shut down first.  assert that the first and second fire
        # only once, and that the third never fires.
        s = self.store

        t1 = TestEvent(testCase=self,
                       name=u't1',
                       store=s, runAgain=None)
        t2 = TestEvent(testCase=self,
                       name=u't2',
                       store=s, runAgain=2)
        t3 = TestEvent(testCase=self,
                       name=u't3',
                       store=s, runAgain=None)

        now = self.now()
        self.ts = [t1, t2, t3]

        S = IScheduler(s)

        # Schedule them out of order to make sure behavior doesn't
        # depend on tasks arriving in soonest-to-latest order.
        S.schedule(t2, now + timedelta(seconds=3))
        S.schedule(t1, now + timedelta(seconds=1))
        S.schedule(t3, now + timedelta(seconds=100))

        self.clock.pump([2, 2, 2])
        self.assertEqual(t1.runCount, 1)
        self.assertEqual(t2.runCount, 2)
        self.assertEqual(t3.runCount, 0)


    def test_unscheduling(self):
        """
        Test the unscheduleFirst method of the scheduler.
        """
        d = Deferred()
        sch = IScheduler(self.store)
        t1 = TestEvent(testCase=self, name=u't1', store=self.store)
        t2 = TestEvent(testCase=self, name=u't2', store=self.store, runAgain=None)

        sch.schedule(t1, self.now() + timedelta(seconds=1))
        sch.schedule(t2, self.now() + timedelta(seconds=2))
        sch.unscheduleFirst(t1)
        self.clock.advance(3)
        self.assertEquals(t1.runCount, 0)
        self.assertEquals(t2.runCount, 1)


    def test_inspection(self):
        """
        Test that the L{scheduledTimes} method returns an iterable of all the
        times at which a particular item is scheduled to run.
        """
        now = self.now() + timedelta(seconds=1)
        off = timedelta(seconds=3)
        sch = IScheduler(self.store)
        runnable = TestEvent(store=self.store, name=u'Only event')
        sch.schedule(runnable, now)
        sch.schedule(runnable, now + off)
        sch.schedule(runnable, now + off + off)

        self.assertEquals(
            list(sch.scheduledTimes(runnable)),
            [now, now + off, now + off + off])


    def test_scheduledTimesDuringRun(self):
        """
        L{Scheduler.scheduledTimes} should not include scheduled times that have
        already triggered.
        """
        futureTimes = []
        scheduler = IScheduler(self.store)
        runner = HookRunner(
            store=self.store,
            hook=lambda self: futureTimes.append(
                list(scheduler.scheduledTimes(self))))

        then = self.now() + timedelta(seconds=1)
        scheduler.schedule(runner, self.now())
        scheduler.schedule(runner, then)
        self.clock.advance(1)
        self.assertEquals(futureTimes, [[then], []])


    def test_deletedRunnable(self):
        """
        Verify that if a scheduled item is deleted,
        L{TimedEvent.invokeRunnable} just deletes the L{TimedEvent} without
        raising an exception.
        """
        now = self.now()
        scheduler = IScheduler(self.store)
        runnable = TestEvent(store=self.store, name=u'Only event')
        scheduler.schedule(runnable, now)

        runnable.deleteFromStore()

        # Invoke it manually to avoid timing complexity.
        timedEvent = self.store.findUnique(
            TimedEvent, TimedEvent.runnable == runnable)
        timedEvent.invokeRunnable()

        self.assertEqual(
            self.store.findUnique(
                TimedEvent,
                TimedEvent.runnable == runnable,
                default=None),
            None)



class TopStoreSchedTest(SchedTest, TestCase):
    def setUp(self):
        self.store = self.siteStore = Store()
        super(TopStoreSchedTest, self).setUp()


    def testBasicScheduledError(self):
        S = IScheduler(self.store)
        S.schedule(NotActuallyRunnable(store=self.store), self.now())

        te = TestEvent(store=self.store, testCase=self,
                       name=u't1', runAgain=None)
        S.schedule(te, self.now() + timedelta(seconds=1))

        self.assertEquals(
            self.store.query(TimedEventFailureLog).count(), 0)

        self.clock.advance(3)

        self.assertEquals(te.runCount, 1)

        errs = self.flushLoggedErrors(AttributeError)
        self.assertEquals(len(errs), 1)
        self.assertEquals(self.store.query(TimedEventFailureLog).count(), 1)

    def testScheduledErrorWithHandler(self):
        S = IScheduler(self.store)
        spec = SpecialErrorHandler(store=self.store)
        S.schedule(spec, self.now())

        te = TestEvent(store=self.store, testCase=self,
                       name=u't1', runAgain=None)
        S.schedule(te, self.now() + timedelta(seconds=1))
        self.assertEquals(
            self.store.query(TimedEventFailureLog).count(), 0)

        self.clock.advance(3)

        self.assertEquals(te.runCount, 1)

        errs = self.flushLoggedErrors(SpecialError)
        self.assertEquals(len(errs), 1)
        self.assertEquals(self.store.query(TimedEventFailureLog).count(), 0)
        self.failUnless(spec.procd)
        self.failIf(spec.broken)



class SubSchedulerTests(SchedTest, TestCase):
    """
    Tests for the substore implementation of IScheduler.
    """
    def setUp(self):
        """
        Create a site store for the substore which will contain the IScheduler
        being tested.  Start its IService so any scheduled events will run.
        """
        self.storePath = filepath.FilePath(self.mktemp())
        self.siteStore = Store(self.storePath)
        super(SubSchedulerTests, self).setUp()

        substoreItem = SubStore.createNew(self.siteStore, ['scheduler_test'])
        self.substore = substoreItem.open()
        self.scheduler = scheduler = IScheduler(self.substore)
        self.stubTime(scheduler)

        self.store = self.substore


    def test_now(self):
        """
        The user store's L{IScheduler} powerup's C{now} method returns whatever
        the site store's L{IScheduler} powerup's C{now} method returns.
        """
        # I don't want the stubbed now method.
        del self.scheduler.now

        self.clock.advance(17)
        self.assertEquals(
            self.scheduler.now(),
            Time.fromPOSIXTimestamp(self.clock.seconds()))


    def test_scheduleAfterParentHookError(self):
        """
        A transient error during a L{_SubSchedulerParentHook} run (such as
        failing to open the substore for whatever reason) should not disable
        subsequent scheduling.
        """
        runnable = TestEvent(store=self.store)

        # Schedule runnable, but fail the _SubSchedulerParentHook run.

        self.scheduler.schedule(runnable, self.now() + timedelta(seconds=1))
        hook = self.siteStore.findUnique(_SubSchedulerParentHook)
        def stumble():
            raise IOError('Denied')
        object.__setattr__(hook, 'run', stumble)
        self.clock.advance(1)
        object.__delattr__(hook, 'run')

        self.assertEquals(
            self.siteStore.findUnique(TimedEventFailureLog).runnable,
            hook)
        [err] = self.flushLoggedErrors(IOError)
        self.assertEquals(str(err.value), 'Denied')
        self.assertEquals(runnable.runCount, 0)

        # Schedule runnable again.  The restored hook in the site store should
        # trigger both scheduled runs in the substore now.

        self.scheduler.schedule(runnable, self.now() + timedelta(seconds=1))
        self.clock.advance(1)
        self.assertEquals(runnable.runCount, 2)



class SchedulerStartupTests(TestCase):
    """
    Tests for behavior relating to L{Scheduler} service startup.
    """
    def setUp(self):
        self.clock = Clock()
        self.store = Store()


    def tearDown(self):
        return self.stopStoreService()


    def now(self):
        return Time.fromPOSIXTimestamp(self.clock.seconds())


    def time(self, offset):
        return self.now() + timedelta(seconds=offset)


    def makeScheduler(self):
        """
        Create, install, and return a Scheduler with a fake callLater.
        """
        scheduler = IScheduler(self.store)
        scheduler.callLater = self.clock.callLater
        scheduler.now = self.now
        return scheduler


    def startStoreService(self):
        """
        Start the Store Service.
        """
        service = IService(self.store)
        service.startService()


    def stopStoreService(self):
        service = IService(self.store)
        if service.running:
            return service.stopService()


    def test_scheduleWhileStopped(self):
        """
        Test that a schedule call on a L{Scheduler} which has not been started
        does not result in the creation of a transient timed event.
        """
        scheduler = self.makeScheduler()
        scheduler.schedule(TestEvent(store=self.store), self.time(1))
        self.assertEqual(self.clock.calls, [])


    def test_scheduleWithRunningService(self):
        """
        Test that if a scheduler is created and installed on a store which has
        a started service, a transient timed event is created when the scheduler
        is used.
        """
        self.startStoreService()
        scheduler = self.makeScheduler()
        scheduler.schedule(TestEvent(store=self.store), self.time(1))
        self.assertEqual(len(self.clock.calls), 1)


    def test_schedulerStartedWithPastEvent(self):
        """
        Test that an existing Scheduler with a TimedEvent in the past is
        started immediately (but does not run the TimedEvent synchronously)
        when the Store Service is started.
        """
        scheduler = self.makeScheduler()
        scheduler.schedule(TestEvent(store=self.store), self.time(-1))
        self.assertEqual(self.clock.calls, [])
        self.startStoreService()
        self.assertEqual(len(self.clock.calls), 1)


    def test_schedulerStartedWithFutureEvent(self):
        """
        Test that an existing Scheduler with a TimedEvent in the future is
        started immediately when the Store Service is started.
        """
        scheduler = self.makeScheduler()
        scheduler.schedule(TestEvent(store=self.store), self.time(1))
        self.assertEqual(self.clock.calls, [])
        self.startStoreService()
        self.assertEqual(len(self.clock.calls), 1)


    def test_schedulerStopped(self):
        """
        Test that when the Store Service is stopped, the Scheduler's transient
        timed event is cleaned up.
        """
        self.test_scheduleWithRunningService()
        d = self.stopStoreService()
        def cbStopped(ignored):
            self.assertEqual(self.clock.calls, [])
        d.addCallback(cbStopped)
        return d



class MissingService(unittest.TestCase):
    """
    A set of tests to verify that things *aren't* scheduled with the reactor
    when the scheduling service doesn't exist, merely persisted to the
    database.
    """

    def setUp(self):
        """
        Create a store with a scheduler installed on it and hook the C{now} and
        C{callLater} methods of that scheduler so their behavior can be
        controlled by these tests.
        """
        self.calls = []
        self.store = Store(filepath.FilePath(self.mktemp()))
        self.siteScheduler = IScheduler(self.store)
        self.siteScheduler.callLater = self._callLater


    def _callLater(self, s, f, *a, **k):
        self.calls.append((s, f, a, k))


    def test_schedule(self):
        """
        Test that if an event is scheduled against a scheduler which is not
        running, not transient scheduling (eg, reactor.callLater) is performed.
        """
        return self._testSchedule(self.siteScheduler)


    def test_subSchedule(self):
        """
        The same as test_schedule, except using a subscheduler.
        """
        subst = SubStore.createNew(self.store, ['scheduler_test'])
        substore = subst.open()
        subscheduler = IScheduler(substore)
        return self._testSchedule(subscheduler)


    def _testSchedule(self, scheduler):
        t1 = TestEvent(store=scheduler.store)
        scheduler.schedule(t1, Time.fromPOSIXTimestamp(0))
        self.failIf(self.calls,
                    "Should not have had any calls: %r" % (self.calls,))
        self.assertIdentical(
            scheduler._getNextEvent(Time.fromPOSIXTimestamp(1)).runnable, t1)



class ScheduleCallingItem(Item):
    """
    Item which invokes C{schedule} on its store's L{IScheduler} from its own
    C{run} method.
    """

    ran = boolean(default=False)
    rescheduleFor = timestamp()

    def run(self):
        scheduler = IScheduler(self.store)
        scheduler.schedule(self, self.rescheduleFor)
        self.ran = True



class NullRunnable(Item):
    """
    Runnable item which does nothing.
    """
    ran = boolean(default=False)

    def run(self):
        pass



class SubStoreSchedulerReentrancy(TestCase):
    """
    Test re-entrant scheduling calls on an item run by a SubScheduler.
    """
    def setUp(self):
        self.clock = Clock()

        self.dbdir = filepath.FilePath(self.mktemp())
        self.store = Store(self.dbdir)
        self.substoreItem = SubStore.createNew(self.store, ['sub'])
        self.substore = self.substoreItem.open()

        self.scheduler = IScheduler(self.store)
        self.subscheduler = IScheduler(self.substore)

        self.scheduler.callLater = self.clock.callLater
        self.scheduler.now = lambda: Time.fromPOSIXTimestamp(self.clock.seconds())
        self.subscheduler.now = lambda: Time.fromPOSIXTimestamp(self.clock.seconds())

        IService(self.store).startService()


    def tearDown(self):
        return IService(self.store).stopService()


    def _scheduleRunner(self, now, offset):
        scheduledAt = Time.fromPOSIXTimestamp(now + offset)
        rescheduleFor = Time.fromPOSIXTimestamp(now + offset + 10)
        runnable = ScheduleCallingItem(store=self.substore, rescheduleFor=rescheduleFor)
        self.subscheduler.schedule(runnable, scheduledAt)
        return runnable


    def testSchedule(self):
        """
        Test the schedule method, as invoked from the run method of an item
        being run by the subscheduler.
        """
        now = self.clock.seconds()
        runnable = self._scheduleRunner(now, 10)

        self.clock.advance(11)

        self.assertEqual(
            list(self.subscheduler.scheduledTimes(runnable)),
            [Time.fromPOSIXTimestamp(now + 20)])

        hook = self.store.findUnique(
            _SubSchedulerParentHook,
            _SubSchedulerParentHook.subStore == self.substoreItem)

        self.assertEqual(
            list(self.scheduler.scheduledTimes(hook)),
            [Time.fromPOSIXTimestamp(now + 20)])


    def testScheduleWithLaterTimedEvents(self):
        """
        Like L{testSchedule}, but use a SubScheduler which has pre-existing
        TimedEvents which are beyond the new runnable's scheduled time (to
        trigger the reschedule-using code-path in
        _SubSchedulerParentHook._schedule).
        """
        now = self.clock.seconds()
        when = Time.fromPOSIXTimestamp(now + 30)
        null = NullRunnable(store=self.substore)
        self.subscheduler.schedule(null, when)
        runnable = self._scheduleRunner(now, 10)

        self.clock.advance(11)

        self.assertEqual(
            list(self.subscheduler.scheduledTimes(runnable)),
            [Time.fromPOSIXTimestamp(now + 20)])

        self.assertEqual(
            list(self.subscheduler.scheduledTimes(null)),
            [Time.fromPOSIXTimestamp(now + 30)])

        hook = self.store.findUnique(
            _SubSchedulerParentHook,
            _SubSchedulerParentHook.subStore == self.substoreItem)

        self.assertEqual(
            list(self.scheduler.scheduledTimes(hook)),
            [Time.fromPOSIXTimestamp(20)])


    def testScheduleWithEarlierTimedEvents(self):
        """
        Like L{testSchedule}, but use a SubScheduler which has pre-existing
        TimedEvents which are before the new runnable's scheduled time.
        """
        now = self.clock.seconds()
        when = Time.fromPOSIXTimestamp(now + 15)
        null = NullRunnable(store=self.substore)
        self.subscheduler.schedule(null, when)
        runnable = self._scheduleRunner(now, 10)

        self.clock.advance(11)

        self.assertEqual(
            list(self.subscheduler.scheduledTimes(runnable)),
            [Time.fromPOSIXTimestamp(now + 20)])

        self.assertEqual(
            list(self.subscheduler.scheduledTimes(null)),
            [Time.fromPOSIXTimestamp(now + 15)])

        hook = self.store.findUnique(
            _SubSchedulerParentHook,
            _SubSchedulerParentHook.subStore == self.substoreItem)

        self.assertEqual(
            list(self.scheduler.scheduledTimes(hook)),
            [Time.fromPOSIXTimestamp(now + 15)])


    def testMultipleEventsPerTick(self):
        """
        Test running several runnables in a single tick of the subscheduler.
        """
        now = self.clock.seconds()
        runnables = [
            self._scheduleRunner(now, 10),
            self._scheduleRunner(now, 11),
            self._scheduleRunner(now, 12)]

        self.clock.advance(13)

        for n, runnable in enumerate(runnables):
            self.assertEqual(
                list(self.subscheduler.scheduledTimes(runnable)),
                [Time.fromPOSIXTimestamp(now + n + 20)])

        hook = self.store.findUnique(
            _SubSchedulerParentHook,
            _SubSchedulerParentHook.subStore == self.substoreItem)

        self.assertEqual(
            list(self.scheduler.scheduledTimes(hook)),
            [Time.fromPOSIXTimestamp(now + 20)])



class BackwardsCompatibilitySchedTests(object):
    """
    L{Scheduler} and L{SubScheduler} are going to be removed.  In the mean
    time, if someone gets their hands on one and tries to do something
    supported to it, it should be as if they were doing it to the suitable
    replacement, L{_SiteScheduler} or L{_UserScheduler}.  This mixin provides
    tests for that behavior, as well as for the deprecations of L{Scheduler}
    and L{SubScheduler}.

    @ivar schedulerType: L{Scheduler} or L{SubScheduler}, whichever is to be
        tested.
    """
    def setUp(self):
        """
        Create a store with an instance of C{self.schedulerType} in it.
        """
        self.store = Store()
        self.oldScheduler = self.schedulerType(store=self.store)
        warnings = self.flushWarnings([self.setUp])
        self.assertEquals(len(warnings), 1)
        self.assertEquals(warnings[0]['category'], PendingDeprecationWarning)
        self.assertEquals(
            warnings[0]['message'],
            self.schedulerType.__name__ + " is deprecated since Axiom 0.5.32.  "
            "Just adapt stores to IScheduler.")
        self.scheduler = IScheduler(self.store)


    def _checkSynonym(self, name):
        # Whatever the value of the attribute is on the _SiteScheduler or
        # _UserScheduler instance, that's what it should be on the Scheduler
        # or SubScheduler Item.
        foo = object()
        setattr(self.scheduler, name, foo)
        self.assertIdentical(getattr(self.oldScheduler, name), foo)

        # And rebinding the attribute on the (Sub)Scheduler Item should rebind it on
        # the _SiteScheduler instance.
        bar = object()
        setattr(self.oldScheduler, name, bar)
        self.assertIdentical(getattr(self.scheduler, name), bar)


    def test_now(self):
        """
        L{Scheduler.now} is a synonym for L{_SiteScheduler.now}.
        """
        self._checkSynonym("now")


    def test_tick(self):
        """
        L{Scheduler.tick} is a synonym for L{_SiteScheduler.tick}.
        """
        self._checkSynonym("tick")


    def test_schedule(self):
        """
        L{Scheduler.schedule} is a synonym for L{_SiteScheduler.schedule}.
        """
        self._checkSynonym("schedule")


    def test_scheduledTimes(self):
        """
        L{Scheduler.scheduledTimes} is a synonym for
        L{_SiteScheduler.scheduledTimes}.
        """
        self._checkSynonym("scheduledTimes")


    def test_unscheduleAll(self):
        """
        L{Scheduler.unscheduleAll} is a synonym for
        L{_SiteScheduler.unscheduleAll}.
        """
        self._checkSynonym("unscheduleAll")


    def test_reschedule(self):
        """
        L{Scheduler.reschedule} is a synonym for
        L{_SiteScheduler.reschedule}.
        """
        self._checkSynonym("reschedule")


    def test_deprecated(self):
        """
        Loading an existing L{Scheduler} from a L{Store} emits a deprecation
        warning.
        """
        storeID = self.oldScheduler.storeID
        del self.oldScheduler
        gc.collect()
        scheduler = self.store.getItemByID(storeID)
        warnings = self.flushWarnings([self.test_deprecated])
        self.assertEquals(len(warnings), 1)
        self.assertEquals(warnings[0]['category'], PendingDeprecationWarning)
        self.assertEquals(
            warnings[0]['message'],
            self.schedulerType.__name__ + " is deprecated since Axiom 0.5.32.  "
            "Just adapt stores to IScheduler.")



class BackwardsCompatibilitySchedulerTests(BackwardsCompatibilitySchedTests, TestCase):
    schedulerType = Scheduler

    def test_interface(self):
        """
        L{Scheduler} provides L{IScheduler} (which it proxies) and
        L{IService} (which is a no-op).
        """
        self.assertTrue(IScheduler.providedBy(self.oldScheduler))
        self.assertTrue(IService.providedBy(self.oldScheduler))



class BackwardsCompatibilitySubSchedulerTests(BackwardsCompatibilitySchedTests, TestCase):
    schedulerType = SubScheduler

    def test_interface(self):
        """
        L{SubScheduler} provides L{IScheduler} (which it proxies).
        """
        self.assertTrue(IScheduler.providedBy(self.oldScheduler))
