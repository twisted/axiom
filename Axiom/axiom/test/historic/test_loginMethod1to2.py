
from twisted.cred.portal import Portal, IRealm

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import UsernamePassword

from axiom.test.test_userbase import IGarbage

from axiom.test.historic import stubloader

CREDENTIALS = (u'test', u'example.com', 'secret')
GARBAGE_LEVEL = 26

class LoginMethodUpgradeTest(stubloader.StubbedTest):
    def testUpgrade(self):
        p = Portal(IRealm(self.store),
                   [ICredentialsChecker(self.store)])

        def loggedIn((interface, avatarAspect, logout)):
            # if we can login, i guess everything is fine
            self.assertEquals(avatarAspect.garbage, GARBAGE_LEVEL)

        creds = UsernamePassword('@'.join(CREDENTIALS[:-1]), CREDENTIALS[-1])
        d = p.login(creds, None, IGarbage)
        return d.addCallback(loggedIn)
