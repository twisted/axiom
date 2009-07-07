
"""
Tests for the upgrade of Scheduler from version 1 to version 2, in which it was
largely supplanted by L{_SiteScheduler}.
"""

from axiom.iaxiom import IScheduler
from axiom.scheduler import Scheduler, _SiteScheduler
from axiom.test.historic.stubloader import StubbedTest


class SchedulerUpgradeTests(StubbedTest):
    def test_powerdown(self):
        """
        The L{Scheduler} created by the stub is powered down by the upgrade and
        adapting the L{Store} to L{IScheduler} succeeds with an instance of
        L{_SiteScheduler}.
        """
        scheduler = self.store.findUnique(Scheduler)
        self.assertEquals(list(self.store.interfacesFor(scheduler)), [])
        self.assertIsInstance(IScheduler(self.store), _SiteScheduler)
