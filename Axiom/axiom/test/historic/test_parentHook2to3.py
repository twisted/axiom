"""
Test upgrading L{_SubSchedulerParentHook} from version 2 to 3.
"""
from axiom.test.historic.stubloader import StubbedTest

from axiom.scheduler import Scheduler, _SubSchedulerParentHook
from axiom.substore import SubStore


class SubSchedulerParentHookUpgradeTests(StubbedTest):
    """
    Test upgrading L{_SubSchedulerParentHook} from version 2 to 3.
    """

    def test_attributesCopied(self):
        """
        L{_SubSchedulerParentHook} version 2's attributes should have been
        copied over.
        """
        hook = self.store.findUnique(_SubSchedulerParentHook)
        self.assertIdentical(hook.loginAccount, self.store.findUnique(SubStore))
        self.assertIdentical(hook.scheduler, self.store.findUnique(Scheduler))
