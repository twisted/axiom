
from twisted.cred.portal import Portal, IRealm

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import UsernamePassword

from axiom.test.test_userbase import IGarbage

from axiom.test.historic.test_loginMethod1to2 import CREDENTIALS, GARBAGE_LEVEL
from axiom.test.historic.stubloader import StubbedTest
class LoginMethodUpgradeTest(StubbedTest):
    def testUpgrade(self):
        p = Portal(IRealm(self.store),
                   [ICredentialsChecker(self.store)])

        def loggedIn((interface, avatarAspect, logout)):
            # if we can login, i guess everything is fine
            self.assertEquals(avatarAspect.garbage, GARBAGE_LEVEL)

        creds = UsernamePassword('@'.join(CREDENTIALS[:-1]), CREDENTIALS[-1])
        d = p.login(creds, None, IGarbage)
        return d.addCallback(loggedIn)

