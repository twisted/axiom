# -*- test-case-name: axiom.test.test_scheduler -*-

from twisted.internet import reactor

from twisted.application.service import Service, IService
from twisted.python import log

from epsilon.extime import Time

from axiom.item import Item
from axiom.attributes import AND, timestamp, reference, integer, inmemory
from axiom.iaxiom import IScheduler

class TimedEvent(Item):
    typeName = 'timed_event'
    schemaVersion = 1

    time = timestamp(indexed=True)
    runnable = reference()

class SchedulerMixin:
    def now(self):
        # testing hook
        return Time()

    def tick(self):
        now = self.now()
        any = 0
        self.nextEventAt = None
        before = self.eventsRun
        for event in self.store.query(TimedEvent,
                                      TimedEvent.time < now,
                                      sort=TimedEvent.time.ascending):
            self.eventsRun += 1
            newTime = event.runnable.run()
            if newTime is not None:
                event.time = newTime
            else:
                event.deleteFromStore()
            any = 1
        if any:
            self.lastEventAt = now
        x = list(
            self.store.query(TimedEvent, sort=TimedEvent.time.ascending, limit=1))
        if x:
            self._transientSchedule(x[0].time, now)
        log.msg("%r ran %d events" % (self, self.eventsRun - before,))

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


class Scheduler(Item, Service, SchedulerMixin):

    typeName = 'axiom_scheduler'
    schemaVersion = 1

    parent = inmemory()
    running = inmemory()
    name = inmemory()
    timer = inmemory()

    eventsRun = integer()
    lastEventAt = timestamp()
    nextEventAt = timestamp()

    def __init__(self, **kw):
        super(Scheduler, self).__init__(**kw)
        self.eventsRun = 0
        self.lastEventAt = None
        self.nextEventAt = None

    def __repr__(self):
        return '<Scheduler>'

    def activate(self):
        self.timer = None
        self.running = False

    def installOn(self, other):
        other.powerUp(self, IService)
        other.powerUp(self, IScheduler)

    def startService(self):
        super(Scheduler, self).startService()
        self.store.transact(self.tick)

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
                                    self.store.transact, self.tick)
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
