
from twisted.cred.portal import Portal, IRealm

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import UsernamePassword

from axiom.test.test_userbase import IGarbage

from axiom.test.historic import stubloader

CREDENTIALS = ('test', 'example.com', 'secret')
GARBAGE_LEVEL = 26

class LoginMethodUpgradeTest(stubloader.StubbedTest):
    def testUpgrade(self):
        p = Portal(IRealm(self.store),
                   [ICredentialsChecker(self.store)])

        def loggedIn(xxx_todo_changeme):
            # if we can login, i guess everything is fine
            (interface, avatarAspect, logout) = xxx_todo_changeme
            self.assertEqual(avatarAspect.garbage, GARBAGE_LEVEL)

        creds = UsernamePassword('@'.join(CREDENTIALS[:-1]), CREDENTIALS[-1])
        d = p.login(creds, None, IGarbage)
        return d.addCallback(loggedIn)
