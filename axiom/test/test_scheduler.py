

from datetime import timedelta

from twisted.trial import unittest
from twisted.application.service import IService
from twisted.internet.defer import Deferred

from axiom.scheduler import Scheduler
from axiom.store import Store
from axiom.item import Item

from axiom.attributes import integer, inmemory
from axiom.extime import Time


class TestEvent(Item):

    typeName = 'test_event'
    schemaVersion = 1

    deferred = inmemory()       # these won't fall out of memory due to
                                # caching, thanks.
    testCase = inmemory()

    maxRunCount = integer()     # fail the test if we run more than this many
                                # times
    runCount = integer()
    runAgain = integer()        # seconds to add, then run again

    def __init__(self, **kw):
        self.deferred = None
        super(TestEvent, self).__init__(**kw)
        self.runCount = 0

    def run(self):
        self.runCount += 1
        if self.runCount > self.maxRunCount:
            self.testCase.fail("%d ran too many times"% (self.storeID))
        if self.runAgain is not None:
            result = Time() + timedelta(seconds=self.runAgain)
            self.runAgain = None
        else:
            if self.deferred is not None:
                self.deferred.callback('done')
            result = None
        return result

class SchedTest(unittest.TestCase):

    def setUp(self):
        self.store = Store()
        self.sched = Scheduler(store=self.store)
        self.sched.install()
        IService(self.store).startService()

    def testScheduler(self):
        # create 3 timed events.  the first one fires.  the second one fires,
        # then reschedules itself.  the third one should never fire because the
        # reactor is shut down first.  assert that the first and second fire
        # only once, and that the third never fires.

        s = self.store
        d = Deferred()

        interval = 0.1

        t1 = TestEvent(testCase=self,
                       store=s, maxRunCount=1, runAgain=None)
        t2 = TestEvent(testCase=self,
                       store=s, maxRunCount=2, runAgain=interval, deferred=d)
        t3 = TestEvent(testCase=self,
                       store=s, maxRunCount=0, runAgain=None)

        now = Time()
        self.ts = [t1, t2, t3]

        self.sched.schedule(t1, now + timedelta(seconds=interval * 1))
        self.sched.schedule(t2, now + timedelta(seconds=interval * 2))
        self.sched.schedule(t3, now + timedelta(seconds=interval * 20))

        return d

    def tearDown(self):
        IService(self.store).stopService()
