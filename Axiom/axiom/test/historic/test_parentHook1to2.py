
from axiom.test.historic.stubloader import StubbedTest

from axiom.scheduler import Scheduler, _SubSchedulerParentHook


class SubSchedulerParentHookUpgradeTests(StubbedTest):
    """
    Test that a sub-scheduler's parent hook is upgraded to include a reference
    to the site scheduler.
    """
    def test_schedulerAttribute(self):
        hook = self.store.findUnique(_SubSchedulerParentHook)
        scheduler = self.store.findUnique(Scheduler)
        self.assertIdentical(hook.scheduler, scheduler)
