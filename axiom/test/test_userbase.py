
from zope.interface import Interface, implements
from twisted.trial import unittest

from twisted.cred.portal import Portal, IRealm
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import UsernamePassword
from twisted.python.filepath import FilePath

from axiom.store import Store
from axiom.substore import SubStore
from axiom.userbase import LoginSystem, getAccountNames, extractUserStore, insertUserStore
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

class AccountTestCase(unittest.TestCase):
    def testAccountNames(self):
        dbdir = self.mktemp()
        s = Store(dbdir)
        ls = LoginSystem(store=s)
        ls.installOn(s)
        acc = ls.addAccount('username', 'dom.ain', 'password')
        ss = acc.avatars.open()

        self.assertEquals(
            list(getAccountNames(ss)),
            [('username', 'dom.ain')])

        secAcc = ls.addAccount('nameuser', 'ain.dom', 'wordpass', acc.avatars)

        names = list(getAccountNames(ss))
        names.sort()
        self.assertEquals(
            names,
            [('nameuser', 'ain.dom'), ('username', 'dom.ain')])

class ThingThatMovesAround(Item):
    typeName = 'test_thing_that_moves_around'
    schemaVersion = 1

    superValue = integer()

class SubStoreMigrationTestCase(unittest.TestCase):

    IMPORTANT_VALUE = 159

    def setUp(self):
        self.dbdir = self.mktemp()
        self.store = Store(self.dbdir)
        self.ls = LoginSystem(store=self.store)

        self.account = self.ls.addAccount(u'testuser', u'localhost', u'PASSWORD')

        accountStore = self.account.avatars.open()

        ThingThatMovesAround(store=accountStore, superValue=self.IMPORTANT_VALUE)

        self.origdir = accountStore.dbdir
        self.destdir = FilePath(self.mktemp())

    def testExtraction(self):
        extractUserStore(self.account, self.destdir)
        self.assertEquals(
            self.ls.accountByAddress(u'testuser', u'localhost'),
            None)

        self.failIf(list(self.store.query(SubStore, SubStore.storepath == self.origdir)))
        self.origdir.restat(False)
        self.failIf(self.origdir.exists())

    def testInsertion(self, _deleteDomainDirectory=False):
        self.testExtraction()

        if _deleteDomainDirectory:
            self.store.filesdir.child('account').child('localhost').remove()

        insertUserStore(self.store, self.destdir)
        insertedStore = self.ls.accountByAddress(u'testuser', u'localhost').avatars.open()
        self.assertEquals(
            insertedStore.findUnique(ThingThatMovesAround).superValue,
            self.IMPORTANT_VALUE)

    def testInsertionWithNoDomainDirectory(self):
        self.testInsertion(True)
