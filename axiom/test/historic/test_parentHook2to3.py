
"""
Test upgrading L{_SubSchedulerParentHook} from version 2 to 3.
"""

from axiom.test.historic.stubloader import StubbedTest

from axiom.scheduler import _SubSchedulerParentHook
from axiom.substore import SubStore
from axiom.dependency import _DependencyConnector


class SubSchedulerParentHookUpgradeTests(StubbedTest):
    """
    Test upgrading L{_SubSchedulerParentHook} from version 2 to 3.
    """
    def setUp(self):
        d = StubbedTest.setUp(self)
        def cbSetUp(ignored):
            self.hook = self.store.findUnique(_SubSchedulerParentHook)
        d.addCallback(cbSetUp)
        return d


    def test_attributesCopied(self):
        """
        The only attribute of L{_SubSchedulerParentHook} which still exists at
        the current version, version 4, C{subStore}, ought to have been
        copied over.
        """
        self.assertIdentical(
            self.hook.subStore, self.store.findUnique(SubStore))


    def test_uninstalled(self):
        """
        The record of the installation of L{_SubSchedulerParentHook} on the
        store is deleted in the upgrade to schema version 4.
        """
        self.assertEquals(
            list(self.store.query(
                    _DependencyConnector,
                    _DependencyConnector.installee == self.hook)),
            [])
