# -*- test-case-name: axiom.test.test_scheduler -*-

from zope.interface import implements

from twisted.internet import reactor

from twisted.application.service import Service, IService
from twisted.python import log, failure

from epsilon.extime import Time
from epsilon import descriptor

from axiom.item import Item
from axiom.attributes import AND, timestamp, reference, integer, inmemory, bytes
from axiom.dependency import dependsOn, installOn
from axiom.iaxiom import IScheduler
from axiom.upgrade import registerUpgrader

VERBOSE = False

class TimedEventFailureLog(Item):
    typeName = 'timed_event_failure_log'
    schemaVersion = 1

    desiredTime = timestamp()
    actualTime = timestamp()

    runnable = reference()
    traceback = bytes()


class TimedEvent(Item):
    typeName = 'timed_event'
    schemaVersion = 1

    time = timestamp(indexed=True)
    runnable = reference()

    def _rescheduleFromRun(self, newTime):
        """
        Schedule this event to be run at the indicated time, or if the
        indicated time is None, delete this event.
        """
        if newTime is None:
            self.deleteFromStore()
        else:
            self.time = newTime


    def invokeRunnable(self):
        """
        Run my runnable, and reschedule or delete myself based on its result.
        Must be run in a transaction.
        """
        runnable = self.runnable
        if runnable is None:
            self.deleteFromStore()
        else:
            self._rescheduleFromRun(runnable.run())


    def handleError(self, now, failureObj):
        """ An error occurred running my runnable.  Check my runnable for an
        error-handling method called 'timedEventErrorHandler' that will take
        the given failure as an argument, and execute that if available:
        otherwise, create a TimedEventFailureLog with information about what
        happened to this event.

        Must be run in a transaction.
        """
        errorHandler = getattr(self.runnable, 'timedEventErrorHandler', None)
        if errorHandler is not None:
            self._rescheduleFromRun(errorHandler(self, failureObj))
        else:
            self._defaultErrorHandler(now, failureObj)


    def _defaultErrorHandler(self, now, failureObj):
        tefl = TimedEventFailureLog(store=self.store,
                                    desiredTime=self.time,
                                    actualTime=now,
                                    runnable=self.runnable,
                                    traceback=failureObj.getTraceback())
        self.deleteFromStore()



class _WackyControlFlow(Exception):
    def __init__(self, eventObject, failureObject):
        Exception.__init__(self, "User code failed during timed event")
        self.eventObject = eventObject
        self.failureObject = failureObject


MAX_WORK_PER_TICK = 10

class SchedulerMixin:
    def _oneTick(self, now):
        theEvent = self._getNextEvent(now)
        if theEvent is None:
            return False
        try:
            theEvent.invokeRunnable()
        except:
            raise _WackyControlFlow(theEvent, failure.Failure())
        self.lastEventAt = now
        return True


    def _getNextEvent(self, now):
        # o/` gonna party like it's 1984 o/`
        theEventL = list(self.store.query(TimedEvent,
                                          TimedEvent.time <= now,
                                          sort=TimedEvent.time.ascending,
                                          limit=1))
        if theEventL:
            return theEventL[0]


    def tick(self):
        now = self.now()
        self.nextEventAt = None
        before = self.eventsRun
        workBeingDone = True
        workUnitsPerformed = 0
        errors = 0
        while workBeingDone and workUnitsPerformed < MAX_WORK_PER_TICK:
            try:
                workBeingDone = self.store.transact(self._oneTick, now)
            except _WackyControlFlow, wcf:
                self.store.transact(wcf.eventObject.handleError, now, wcf.failureObject)
                log.err(wcf.failureObject)
                errors += 1
                workBeingDone = True
            if workBeingDone:
                workUnitsPerformed += 1
        x = list(self.store.query(TimedEvent, sort=TimedEvent.time.ascending, limit=1))
        if x:
            self._transientSchedule(x[0].time, now)
        if errors or VERBOSE:
            log.msg("The scheduler ran %(eventCount)s events%(errors)s." % dict(
                    eventCount=workUnitsPerformed,
                    errors=(errors and (" (with %d errors)" % (errors,))) or ''))


    def schedule(self, runnable, when):
        TimedEvent(store=self.store, time=when, runnable=runnable)
        self._transientSchedule(when, self.now())


    def reschedule(self, runnable, fromWhen, toWhen):
        for evt in self.store.query(TimedEvent,
                                    AND(TimedEvent.time == fromWhen,
                                        TimedEvent.runnable == runnable)):
            evt.time = toWhen
            self._transientSchedule(toWhen, self.now())
            break
        else:
            raise ValueError("%r is not scheduled to run at %r" % (runnable, fromWhen))


    def unscheduleFirst(self, runnable):
        """
        Remove from given item from the schedule.

        If runnable is scheduled to run multiple times, only the temporally first
        is removed.
        """
        for evt in self.store.query(TimedEvent, TimedEvent.runnable == runnable, sort=TimedEvent.time.ascending):
            evt.deleteFromStore()
            break


    def unscheduleAll(self, runnable):
        for evt in self.store.query(TimedEvent, TimedEvent.runnable == runnable):
            evt.deleteFromStore()


    def scheduledTimes(self, runnable):
        """
        Return an iterable of the times at which the given item is scheduled to
        run.
        """
        events = self.store.query(
            TimedEvent, TimedEvent.runnable == runnable)
        return events.getColumn("time")

_EPSILON = 1e-20      # A very small amount of time.

class Scheduler(Item, Service, SchedulerMixin):
    """
    Track and execute persistent timed events for a I{site} store.
    """
    typeName = 'axiom_scheduler'
    schemaVersion = 1

    implements(IService, IScheduler)

    powerupInterfaces = (IService, IScheduler)

    parent = inmemory()
    name = inmemory()
    timer = inmemory()

    # Also testing hooks
    callLater = inmemory()
    now = inmemory()

    eventsRun = integer()
    lastEventAt = timestamp()
    nextEventAt = timestamp()

    class running(descriptor.attribute):
        def get(self):
            return (
                self.parent is self.store._axiom_service and
                self.store._axiom_service is not None and
                self.store._axiom_service.running)

        def set(self, value):
            # Eh whatever
            pass


    def __init__(self, **kw):
        super(Scheduler, self).__init__(**kw)
        self.eventsRun = 0
        self.lastEventAt = None
        self.nextEventAt = None


    def __repr__(self):
        return '<Scheduler>'


    def installed(self):
        self.setServiceParent(IService(self.store))


    def activate(self):
        self.timer = None
        self.callLater = reactor.callLater
        self.now = Time


    def startService(self):
        """
        Start calling persistent timed events whose time has come.
        """
        super(Scheduler, self).startService()
        self._transientSchedule(self.now(), self.now())


    def stopService(self):
        """
        Stop calling persistent timed events.
        """
        super(Scheduler, self).stopService()
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None


    def tick(self):
        self.timer = None
        return super(Scheduler, self).tick()


    def _transientSchedule(self, when, now):
        if not self.running:
            return
        if self.timer is not None:
            if self.timer.getTime() < when.asPOSIXTimestamp():
                return
            self.timer.cancel()
        delay = when.asPOSIXTimestamp() - now.asPOSIXTimestamp()

        # reactor.callLater allows only positive delay values.  The scheduler
        # may want to have scheduled things in the past and that's OK, since we
        # are dealing with Time() instances it's impossible to predict what
        # they are relative to the current time from user code anyway.
        delay = max(_EPSILON, delay)
        self.timer = self.callLater(delay, self.tick)
        self.nextEventAt = when


class _SubSchedulerParentHook(Item):
    schemaVersion = 2
    typeName = 'axiom_subscheduler_parent_hook'

    loginAccount = reference()
    scheduledAt = timestamp(default=None)

    scheduler = dependsOn(Scheduler)

    def run(self):
        self.scheduledAt = None
        IScheduler(self.loginAccount).tick()

    def _schedule(self, when):
        if self.scheduledAt is not None:
            if when < self.scheduledAt:
                self.scheduler.reschedule(self, self.scheduledAt, when)
                self.scheduledAt = when
        else:
            self.scheduler.schedule(self, when)
            self.scheduledAt = when


def upgradeParentHook1to2(oldHook):
    """
    Add the scheduler attribute to the given L{_SubSchedulerParentHook}.
    """
    newHook = oldHook.upgradeVersion(
        oldHook.typeName, 1, 2,
        loginAccount=oldHook.loginAccount,
        scheduledAt=oldHook.scheduledAt,
        scheduler=oldHook.store.findFirst(Scheduler))
    return newHook

registerUpgrader(upgradeParentHook1to2, _SubSchedulerParentHook.typeName, 1, 2)


class SubScheduler(Item, SchedulerMixin):
    """
    Track and execute persistent timed events for a substore.
    """
    schemaVersion = 1
    typeName = 'axiom_subscheduler'

    implements(IScheduler)

    powerupInterfaces = (IScheduler,)

    eventsRun = integer(default=0)
    lastEventAt = timestamp()
    nextEventAt = timestamp()

    # Also testing hooks
    callLater = inmemory()
    now = inmemory()

    def __repr__(self):
        return '<SubScheduler for %r>' % (self.store,)


    def activate(self):
        self.callLater = reactor.callLater
        self.now = Time

    def _transientSchedule(self, when, now):
        if self.store.parent is not None:
            loginAccount = self.store.parent.getItemByID(self.store.idInParent)
            hook = self.store.parent.findOrCreate(
                _SubSchedulerParentHook,
                lambda hook: installOn(hook, hook.store),
                loginAccount=loginAccount)
            hook._schedule(when)

    def migrateDown(self):
        """
        Remove the components in the site store for this SubScheduler.
        """
        loginAccount = self.store.parent.getItemByID(self.store.idInParent)
        ssph = self.store.parent.findUnique(_SubSchedulerParentHook,
                           _SubSchedulerParentHook.loginAccount == loginAccount,
                                            default=None)
        if ssph is not None:
            te = self.store.parent.findUnique(TimedEvent,
                                              TimedEvent.runnable == ssph,
                                              default=None)
            if te is not None:
                te.deleteFromStore()
            ssph.deleteFromStore()

    def migrateUp(self):
        """
        Recreate the hooks in the site store to trigger this SubScheduler.
        """
        te = self.store.findFirst(TimedEvent, sort=TimedEvent.time.descending)
        if te is not None:
            self._transientSchedule(te.time, self.now)
