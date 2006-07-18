
from zope.interface import Interface, implements

from twisted.trial import unittest
from twisted.internet.defer import maybeDeferred

from twisted.cred.portal import Portal, IRealm
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import UsernamePassword

from twisted.python.filepath import FilePath

from axiom.store import Store
from axiom.substore import SubStore
from axiom import userbase
from axiom.item import Item
from axiom.attributes import integer
from axiom.scripts import axiomatic
from axiom import errors


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
            l = userbase.LoginSystem(store=s)
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

def pvals(m):
    d = m.persistentValues()
    d.pop('account')
    return d


class AccountTestCase(unittest.TestCase):
    def testAccountNames(self):
        dbdir = self.mktemp()
        s = Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        ls.installOn(s)
        acc = ls.addAccount('username', 'dom.ain', 'password')
        ss = acc.avatars.open()

        self.assertEquals(
            list(userbase.getAccountNames(ss)),
            [('username', 'dom.ain')])

        acc.addLoginMethod(u'nameuser', u'ain.dom')

        names = list(userbase.getAccountNames(ss))
        names.sort()
        self.assertEquals(
            names,
            [('nameuser', 'ain.dom'), ('username', 'dom.ain')])

    def testAvatarStoreState(self):
        """
        You can only pass an 'avatars' argument if it doesn't already have an
        account in it.  Some accounts want to have their stores in slightly odd
        places (like offering.py) but you can't have two accounts added which
        both point to the same store.
        """
        dbdir = self.mktemp()
        s = Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        ls.installOn(s)
        acc = ls.addAccount('alice', 'dom.ain', 'password')

        # this is allowed, if weird
        unrelatedAccount = ls.addAccount(
            'elseice', 'dom.ain', 'password',
            avatars=SubStore.createNew(s, ('crazy', 'what')))

        # this is not allowed.
        self.assertRaises(errors.DuplicateUniqueItem,
                          ls.addAccount,
                          'bob', 'ain.dom', 'xpassword',
                          avatars=acc.avatars)

        # Make sure that our stupid call to addAccount did not corrupt
        # anything, because we are stupid
        self.assertEquals(acc.avatars.open().query(userbase.LoginAccount).count(), 1)


    def testParallelLoginMethods(self):
        dbdir = self.mktemp()
        s = Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        acc = ls.addAccount(u'username', u'example.com', u'password')
        ss = acc.avatars.open()

        loginMethods = s.query(userbase.LoginMethod)
        subStoreLoginMethods = ss.query(userbase.LoginMethod)

        self.assertEquals(loginMethods.count(), 1)
        self.assertEquals(
            [pvals(m) for m in loginMethods],
            [pvals(m) for m in subStoreLoginMethods])


    def testSiteLoginMethodCreator(self):
        dbdir = self.mktemp()
        s = Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        acc = ls.addAccount(u'username', u'example.com', u'password')

        # Do everything twice to make sure repeated calls don't corrupt state
        # somehow
        for i in [0, 1]:
            acc.addLoginMethod(
                localpart=u'anothername',
                domain=u'example.org',
                verified=True,
                protocol=u'test',
                internal=False)

            loginMethods = s.query(
                userbase.LoginMethod, sort=userbase.LoginMethod.storeID.ascending)

            subStoreLoginMethods = acc.avatars.open().query(
                userbase.LoginMethod, sort=userbase.LoginMethod.storeID.ascending)

            self.assertEquals(loginMethods.count(), 2)

            self.assertEquals(
                [pvals(m) for m in loginMethods],
                [pvals(m) for m in subStoreLoginMethods])


    def testUserLoginMethodCreator(self):
        dbdir = self.mktemp()
        s = Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        acc = ls.addAccount(u'username', u'example.com', u'password')
        ss = acc.avatars.open()
        subStoreLoginAccount = ss.findUnique(userbase.LoginAccount)

        # Do everything twice to make sure repeated calls don't corrupt state
        # somehow
        for i in [0, 1]:
            subStoreLoginAccount.addLoginMethod(
                localpart=u'anothername',
                domain=u'example.org',
                verified=True,
                protocol=u'test',
                internal=False)

            loginMethods = s.query(
                userbase.LoginMethod, sort=userbase.LoginMethod.storeID.ascending)

            subStoreLoginMethods = ss.query(
                userbase.LoginMethod, sort=userbase.LoginMethod.storeID.ascending)

            self.assertEquals(loginMethods.count(), 2)

            self.assertEquals(
                [pvals(m) for m in loginMethods],
                [pvals(m) for m in subStoreLoginMethods])


    def testDomainNames(self):
        s = Store()
        acc = s
        for localpart, domain, internal in [
            (u'local', u'example.com', True),
            (u'local', u'example.net', True),
            (u'remote', u'example.org', False),
            (u'another', u'example.com', True),
            (u'brokenguy', None, True)]:
            userbase.LoginMethod(
                store=s,
                localpart=localpart,
                domain=domain,
                verified=True,
                account=s,
                protocol=u'test',
                internal=internal)
        self.assertEquals(userbase.getDomainNames(s), [u"example.com", u"example.net"])



class ThingThatMovesAround(Item):
    typeName = 'test_thing_that_moves_around'
    schemaVersion = 1

    superValue = integer()

class SubStoreMigrationTestCase(unittest.TestCase):

    IMPORTANT_VALUE = 159

    def setUp(self):
        self.dbdir = self.mktemp()
        self.store = Store(self.dbdir)
        self.ls = userbase.LoginSystem(store=self.store)

        self.account = self.ls.addAccount(u'testuser', u'localhost', u'PASSWORD')

        accountStore = self.account.avatars.open()

        ThingThatMovesAround(store=accountStore, superValue=self.IMPORTANT_VALUE)

        self.origdir = accountStore.dbdir
        self.destdir = FilePath(self.mktemp())

    def testExtraction(self):
        userbase.extractUserStore(self.account, self.destdir)
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

        userbase.insertUserStore(self.store, self.destdir)
        insertedStore = self.ls.accountByAddress(u'testuser', u'localhost').avatars.open()
        self.assertEquals(
            insertedStore.findUnique(ThingThatMovesAround).superValue,
            self.IMPORTANT_VALUE)

    def testInsertionWithNoDomainDirectory(self):
        self.testInsertion(True)



class RealmTestCase(unittest.TestCase):
    """
    Tests for the L{IRealm} implementation in L{axiom.userbase}.
    """
    def setUp(self):
        self.store = Store()
        self.realm = userbase.LoginSystem(store=self.store)
        self.realm.installOn(self.store)


    def test_powerup(self):
        """
        Test that L{LoginSystem} powers up the store for L{IRealm}.
        """
        self.assertIdentical(self.realm, IRealm(self.store))


    def test_requestNonexistentAvatarId(self):
        """
        Test that trying to authenticate as a user who does not exist fails
        with a L{NoSuchUser} exception.
        """
        d = maybeDeferred(
            self.realm.requestAvatarId,
            UsernamePassword(u'testuser@example.com', u'password'))
        return self.assertFailure(d, errors.NoSuchUser)


    def test_requestMalformedAvatarId(self):
        """
        Test that trying to authenticate as a user without specifying a
        hostname fails with a L{NoSuchUser} exception.
        """
        d = maybeDeferred(
            self.realm.requestAvatarId,
            UsernamePassword(u'testuser', u'password'))
        return self.assertFailure(d, errors.NoSuchUser)
