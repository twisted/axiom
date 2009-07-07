
"""
Tests for the upgrade of SubScheduler from version 1 to version 2, in which it
was largely supplanted by L{_UserScheduler}.
"""

from axiom.iaxiom import IScheduler
from axiom.scheduler import SubScheduler, _UserScheduler
from axiom.test.historic.stubloader import StubbedTest


class SubSchedulerUpgradeTests(StubbedTest):
    def test_powerdown(self):
        """
        The L{SubScheduler} created by the stub is powered down by the upgrade
        and adapting the L{Store} to L{IScheduler} succeeds with a
        L{_UserScheduler}.
        """
        scheduler = self.store.findUnique(SubScheduler)
        self.assertEquals(list(self.store.interfacesFor(scheduler)), [])

        # Slothfully grant this test store the appearance of being a user
        # store.
        self.store.parent = self.store

        self.assertIsInstance(IScheduler(self.store), _UserScheduler)
