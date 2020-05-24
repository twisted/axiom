
from twisted.internet.defer import Deferred

from axiom.test.historic.stubloader import StubbedTest
from axiom.test.historic.stub_processor1to2 import DummyProcessor

class ProcessorUpgradeTest(StubbedTest):
    def setUp(self):
        # Ick, we need to catch the run event of DummyProcessor, and I can't
        # think of another way to do it.
        self.dummyRun = DummyProcessor.run.__func__
        self.calledBack = Deferred()
        def dummyRun(calledOn):
            self.calledBack.callback(calledOn)
        DummyProcessor.run = dummyRun

        return StubbedTest.setUp(self)


    def tearDown(self):
        # Okay this is a pretty irrelevant method on a pretty irrelevant class,
        # but we'll fix it anyway.
        DummyProcessor.run = self.dummyRun

        return StubbedTest.tearDown(self)


    def test_pollingRemoval(self):
        """
        Test that processors lose their idleInterval but none of the rest of
        their stuff, and that they get scheduled by the upgrader so they can
        figure out what state they should be in.
        """
        proc = self.store.findUnique(DummyProcessor)
        self.assertEqual(proc.busyInterval, 100)
        self.assertNotEqual(proc.scheduled, None)
        def assertion(result):
            self.assertEqual(result, proc)
        return self.calledBack.addCallback(assertion)

