
from twisted.cred.portal import Portal, IRealm

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import UsernamePassword

from axiom.test.test_userbase import IGarbage

from axiom.test.historic import stubloader

SECRET = 'asdf'
SECRET2 = 'ghjk'

class AccountUpgradeTest(stubloader.StubbedTest):
    def testUpgrade(self):
        p = Portal(IRealm(self.store),
                   [ICredentialsChecker(self.store)])

        def loggedIn((ifc, av, lgo)):
            assert av.garbage == 7
            # Bug in cooperator?  this triggers an exception.
            # return svc.stopService()
        d = p.login(
            UsernamePassword('test@example.com', SECRET), None, IGarbage)
        return d.addCallback(loggedIn)
