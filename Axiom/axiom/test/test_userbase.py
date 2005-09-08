
from zope.interface import Interface, implements
from twisted.trial import unittest

from twisted.cred.portal import Portal, IRealm
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import UsernamePassword

from axiom.store import Store
from axiom.userbase import LoginAccount, LoginSystem
from axiom.item import Item
from axiom.attributes import integer
from axiom.scripts import axiomatic


class IGarbage(Interface):
    pass

class GarbageProtocolHandler(Item):
    schemaVersion = 1
    typeName = 'test_login_garbage'

    garbage = integer()

    implements(IGarbage)

    def installOn(self, other):
        other.powerUp(self, IGarbage)

SECRET = 'bananas'

class UserBaseTest(unittest.TestCase):

    def logInAndCheck(self, username, domain='localhost'):
        s = Store(self.mktemp())
        def _speedup():
            l = LoginSystem(store=s)
            l.installOn(s)
            s.checkpoint()
            p = Portal(IRealm(s),
                       [ICredentialsChecker(s)])

            a = l.addAccount(username, 'localhost', SECRET)
            gph = GarbageProtocolHandler(store=a.avatars.open(),
                                         garbage=0)
            gph.installOn(gph.store)
            return p, gph

        p, gph = s.transact(_speedup)

        def wasItGph((interface, avatar, logout)):
            self.assertEquals(interface, IGarbage)
            self.assertEquals(avatar, gph)
            logout()

        return p.login(UsernamePassword('bob@localhost', SECRET), None, IGarbage
                       ).addCallback(wasItGph)

    def testBasicLogin(self):
        self.logInAndCheck('bob')

    def testUppercaseLogin(self):
        self.logInAndCheck('BOB')

    def testMixedCaseLogin(self):
        self.logInAndCheck('BoB')


class CommandTestCase(unittest.TestCase):
    def testUserBaseInstall(self):
        dbdir = self.mktemp()
        axiomatic.main([
                '-d', dbdir, 'userbase', 'install'])

        s = Store(dbdir)
        IRealm(s)
        ICredentialsChecker(s)
        s.close()

    def testUserCreation(self):
        dbdir = self.mktemp()
        axiomatic.main([
                '-d', dbdir, 'userbase',
                'create', 'alice', 'localhost', SECRET])

        s = Store(dbdir)
        cc = ICredentialsChecker(s)
        p = Portal(IRealm(s), [cc])

        def cb((interface, avatar, logout)):
            logout()

        return p.login(UsernamePassword('alice@localhost', SECRET), None, lambda orig, default: orig
                       ).addCallback(cb)
