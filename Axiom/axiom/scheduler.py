# -*- test-case-name: axiom.test.test_scheduler -*-

from twisted.internet import reactor

from twisted.application.service import Service, IService
from twisted.python import log, failure

from epsilon.extime import Time
from epsilon import descriptor

from axiom.item import Item
from axiom.attributes import AND, timestamp, reference, integer, inmemory, bytes
from axiom.iaxiom import IScheduler

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

    def invokeRunnable(self):
        """
        Run my runnable, and reschedule or delete myself based on its result.
        Must be run in a transaction.
        """

        newTime = self.runnable.run()
        if newTime is None:
            self.deleteFromStore()
        else:
            self.time = newTime

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
            errorHandler(self, failureObj)
            self.deleteFromStore()
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
    def now(self):
        # testing hook
        return Time()

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
                                          TimedEvent.time < now,
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
            workUnitsPerformed += 1
            try:
                workBeingDone = self.store.transact(self._oneTick, now)
            except _WackyControlFlow, wcf:
                self.store.transact(wcf.eventObject.handleError, now, wcf.failureObject)
                log.err(wcf.failureObject)
                errors += 1
                workBeingDone = True
        x = list(self.store.query(TimedEvent, sort=TimedEvent.time.ascending, limit=1))
        if x:
            self._transientSchedule(x[0].time, now)
        log.msg("The scheduler ran %(eventCount)s events%(errors)s." % dict(
                eventCount=workUnitsPerformed,
                errors=(errors and (" (with %d errors)" % (errors,))) or ''))

    def schedule(self, runnable, when):
        TimedEvent(store=self.store, time=when, runnable=runnable)
        self._transientSchedule(when, Time())


    def reschedule(self, runnable, fromWhen, toWhen):
        for evt in self.store.query(TimedEvent,
                                    AND(TimedEvent.time == fromWhen,
                                        TimedEvent.runnable == runnable)):
            evt.time = toWhen
            self._transientSchedule(toWhen, Time())
            break
        else:
            raise ValueError("%r is not scheduled to run at %r" % (runnable, fromWhen))


    def unscheduleFirst(self, runnable):
        for evt in self.store.query(TimedEvent, TimedEvent.runnable == runnable, TimedEvent.time.ascending):
            evt.deleteFromStore()
            break


    def unscheduleAll(self, runnable):
        for evt in self.store.query(TimedEvent, TimedEvent.runnable == runnable):
            evt.deleteFromStore()



class Scheduler(Item, Service, SchedulerMixin):

    typeName = 'axiom_scheduler'
    schemaVersion = 1

    parent = inmemory()
    name = inmemory()
    timer = inmemory()

    eventsRun = integer()
    lastEventAt = timestamp()
    nextEventAt = timestamp()


    class running(descriptor.attribute):
        def get(self):
            return self.store.service is not None and self.store.service.running

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

    def activate(self):
        self.timer = None

    def installOn(self, other):
        other.powerUp(self, IService)
        other.powerUp(self, IScheduler)

    def startService(self):
        super(Scheduler, self).startService()
        self.tick()

    def stopService(self):
        super(Scheduler, self).stopService()
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

    def tick(self):
        self.timer = None
        return super(Scheduler, self).tick()

    def callLater(self, s, f, *a, **k):
        s = max(s, 0.00000001)
        return reactor.callLater(s, f, *a, **k)

    def _transientSchedule(self, when, now):
        if not self.running:
            return
        if self.timer is not None:
            if self.timer.getTime() < when.asPOSIXTimestamp():
                return
            self.timer.cancel()
        self.timer = self.callLater(when.asPOSIXTimestamp() - now.asPOSIXTimestamp(),
                                    self.tick)
        self.nextEventAt = when


class _SubSchedulerParentHook(Item):
    schemaVersion = 1
    typeName = 'axiom_subscheduler_parent_hook'

    loginAccount = reference()
    scheduledAt = timestamp(default=None)

    def run(self):
        self.scheduledAt = None
        IScheduler(self.loginAccount).tick()

    def _schedule(self, when):
        sch = IScheduler(self.store)
        if self.scheduledAt is not None:
            if when < self.scheduledAt:
                sch.reschedule(self, self.scheduledAt, when)
        else:
            sch.schedule(self, when)
        self.scheduledAt = when


class SubScheduler(Item, SchedulerMixin):
    schemaVersion = 1
    typeName = 'axiom_subscheduler'

    eventsRun = integer(default=0)
    lastEventAt = timestamp()
    nextEventAt = timestamp()

    def __repr__(self):
        return '<SubScheduler for %r>' % (self.store,)

    def installOn(self, other):
        other.powerUp(self, IScheduler)

    def _transientSchedule(self, when, now):
        loginAccount = self.store.parent.getItemByID(self.store.idInParent)
        hook = self.store.parent.findOrCreate(_SubSchedulerParentHook, loginAccount = loginAccount)
        hook._schedule(when)
