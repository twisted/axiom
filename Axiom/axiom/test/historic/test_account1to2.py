
from twisted.cred.portal import Portal, IRealm
from twisted.application.service import IService

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import UsernamePassword

from axiom.test.test_userbase import IGarbage

from axiom.test.historic import stubloader

SECRET = 'asdf'
SECRET2 = 'ghjk'

class AccountUpgradeTest(stubloader.StubbedTest, ):

    def testUpgrade(self):
        s = self.store
        p = Portal(IRealm(s),
                   [ICredentialsChecker(s)])

        svc = IService(s)
        svc.startService()
        D = s.whenFullyUpgraded()
        def _(fu):
            def __((ifc, av, lgo)):
                assert av.garbage == 7
                # Bug in cooperator?  this triggers an exception.
                # return svc.stopService()
            return p.login(UsernamePassword(
                    'test@example.com', SECRET), None, IGarbage).addCallback(__)
        return D.addCallback(_)
