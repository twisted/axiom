from twisted.cred.portal import Portal, IRealm

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import UsernamePassword

from axiom.test.test_userbase import IGarbage
from axiom.test.historic import stubloader
from axiom.errors import BadCredentials
from axiom.userbase import getTestContext, LoginAccount

SECRET = 'asdf'
SECRET2 = 'ghjk'


class AccountUpgradeTest(stubloader.StubbedTest):
    def test_upgrade(self):
        """
        After the upgrade, logging in with the correct password succeeds, while
        logging in with an incorrect password fails.
        """
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
        self.failureResultOf(d, BadCredentials)

        # Have to let the substore upgrade complete
        return av.store.whenFullyUpgraded()


    def test_password(self):
        """
        After the upgrade, the password attribute is cleared.
        """
        acct = self.store.findUnique(LoginAccount)
        self.assertIdentical(acct.password, None)
