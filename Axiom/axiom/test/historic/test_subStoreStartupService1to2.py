
from axiom.substore import SubStore
from axiom.test.historic.stubloader import StubbedTest

from axiom.test.historic.stub_subStoreStartupService1to2 import DummyService

class UpgradeTest(StubbedTest):
    def testSubStoreServiceStarterStoppedStartingSubStoreServices(self):
        """
        Verify that the sub-store service starter is removed and substore services
        will not be started.

        Also, say that nine times fast.
        """
        ss = self.store.findUnique(SubStore)
        thePowerup = ss.open().findUnique(DummyService)

        # The upgrade stub-loading framework actually takes care of invoking
        # the parent store startService, so we don't have to do that here;
        # let's just make sure that the substore's service wasn't started as
        # part of the upgrade.
        self.failIf(thePowerup.everStarted)
