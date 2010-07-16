
"""
Tests for the upgrade of SubScheduler from version 1 to version 2, in which it
was largely supplanted by L{_UserScheduler}.
"""

from axiom.iaxiom import IScheduler
from axiom.substore import SubStore
from axiom.scheduler import SubScheduler, _UserScheduler
from axiom.test.historic.stubloader import StubbedTest


class SubSchedulerUpgradeTests(StubbedTest):
    def test_powerdown(self):
        """
        The L{SubScheduler} created by the stub is powered down by the upgrade
        and adapting the L{Store} to L{IScheduler} succeeds with a
        L{_UserScheduler}.
        """
        sub = self.store.findFirst(SubStore).open()
        upgraded = sub.whenFullyUpgraded()
        def subUpgraded(ignored):
            scheduler = sub.findUnique(SubScheduler)
            self.assertEquals(list(sub.interfacesFor(scheduler)), [])

            self.assertIsInstance(IScheduler(sub), _UserScheduler)
        upgraded.addCallback(subUpgraded)
        return upgraded
