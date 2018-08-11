from twisted.cred.portal import Portal, IRealm

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import UsernamePassword

from axiom.test.test_userbase import IGarbage
from axiom.test.historic import stubloader
from axiom.errors import BadCredentials
from axiom.userbase import getTestContext

SECRET = 'asdf'
SECRET2 = 'ghjk'


class AccountUpgradeTest(stubloader.StubbedTest):
    def test_upgrade(self):
        ls = IRealm(self.store)
        ls._txCryptContext, perform = getTestContext()
        p = Portal(ls, [ICredentialsChecker(self.store)])
        d = p.login(
            UsernamePassword('test@example.com', SECRET), None, IGarbage)
        perform()
        (ifc, av, lgo) = self.successResultOf(d)
        self.assertEqual(av.garbage, 7)

        d = p.login(
            UsernamePassword('test@example.com', SECRET2), None, IGarbage)
        perform()
        f = self.failureResultOf(d)
        f.trap(BadCredentials)

        # Have to let the substore upgrade complete
        return av.store.whenFullyUpgraded()
