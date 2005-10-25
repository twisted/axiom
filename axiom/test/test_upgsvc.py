
# white-box tests for upgrader service.

from axiom._upgsvc import UpgradeService

from twisted.trial.unittest import TestCase
from twisted.internet.defer import Deferred, DeferredList

from twisted.internet import reactor

class DummyTask:
    keepGoing = 1
    workCount = 0

    def __call__(self):
        assert self.keepGoing
        self.keepGoing -= 1
        self.workCount += 1
        return self.keepGoing


class DeferredTask(DummyTask):
    def __init__(self):
        self.deferred = Deferred()

    def __call__(self):
        result = DummyTask.__call__(self)
        if not result:
            reactor.callLater(0.001, self.deferred.callback, None)
        return result

class SpinTest(TestCase):

    def testWork(self):
        dt = DeferredTask()
        dt.keepGoing = 3
        sp = UpgradeService()
        sp.startService()
        sp.addTask(dt)
        return dt.deferred

    def testWorkWorkWork_StartAfter(self):
        d1 = DeferredTask()
        d2 = DeferredTask()
        d3 = DeferredTask()

        d1.keepGoing = 10
        d2.keepGoing = 3
        d3.keepGoing = 4

        sp = UpgradeService()
        sp.addTask(d1)
        sp.addTask(d2)
        sp.addTask(d3)

        sp.startService()

        return DeferredList([x.deferred for x in [d1, d2, d3]])


    def testWorkWorkWork_StartBefore(self):
        d1 = DeferredTask()
        d2 = DeferredTask()
        d3 = DeferredTask()

        d1.keepGoing = 10
        d2.keepGoing = 3
        d3.keepGoing = 4

        sp = UpgradeService()
        sp.startService()

        sp.addTask(d1)
        sp.addTask(d2)
        sp.addTask(d3)

        return DeferredList([x.deferred for x in [d1, d2, d3]])

    def testWorkWork_Beat_Work(self):
        d1 = DeferredTask()
        d2 = DeferredTask()
        d3 = DeferredTask()

        d1.keepGoing = 10
        d2.keepGoing = 3
        d3.keepGoing = 4

        sp = UpgradeService()
        sp.startService()
        sp.addTask(d1)
        sp.addTask(d2)

        def _(r):
            sp.addTask(d3)
            return d3.deferred

        return DeferredList([d1.deferred, d2.deferred]).addCallback(_)
