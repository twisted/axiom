
from twisted.cred.portal import Portal, IRealm
from twisted.application.service import IService

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import UsernamePassword

from axiom.test.test_userbase import IGarbage

from axiom.test.historic import stubloader

CREDENTIALS = (u'test', u'example.com', 'secret')
GARBAGE_LEVEL = 26

class LoginMethodUpgradeTest(stubloader.StubbedTest):

    def testUpgrade(self):
        s = self.store
        p = Portal(IRealm(s),
                   [ICredentialsChecker(s)])

        svc = IService(s)
        svc.startService()
        D = s.whenFullyUpgraded()

        def upgraded():
            def loggedIn((interface, avatarAspect, logout)):
                assert avatarAspect.garbage == GARBAGE_LEVEL
                # if we can login, i guess everything is fine

            return p.login(UsernamePassword(
                '@'.join(CREDENTIALS[:-1]), CREDENTIALS[-1]),
                None, IGarbage).addCallback(loggedIn)

        return D.addCallback(lambda ign: upgraded())
