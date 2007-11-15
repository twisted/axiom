import datetime, StringIO, sys

from zope.interface import Interface, implements

from twisted.trial import unittest
from twisted.internet.defer import maybeDeferred

from twisted.cred.portal import Portal, IRealm
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import UsernamePassword

from twisted.python.filepath import FilePath

from epsilon.extime import Time

from axiom.store import Store
from axiom.substore import SubStore
from axiom.scheduler import _SubSchedulerParentHook, SubScheduler, Scheduler
from axiom.scheduler import TimedEvent
from axiom import userbase
from axiom.item import Item
from axiom.attributes import integer
from axiom.scripts import axiomatic
from axiom import errors
from axiom import dependency

class IGarbage(Interface):
    pass

class GarbageProtocolHandler(Item):
    schemaVersion = 1
    typeName = 'test_login_garbage'

    powerupInterfaces = (IGarbage,)
    garbage = integer()

    implements(IGarbage)

SECRET = 'bananas'

class UserBaseTest(unittest.TestCase):
    """
    Tests for L{axiom.userbase} with an on-disk store.
    @ivar store: The C{Store} object for the items tested.
    """
    def setUp(self):
        """
        Set up for testing with an on-disk store.
        """
        self.store = Store(self.mktemp())


    def logInAndCheck(self, username, domain='localhost'):
        """
        Ensure that logging in via cred succeeds based on the accounts
        managed by L{axiom.userbase.LoginSystem}.
        """
        s = self.store
        def _speedup():
            l = userbase.LoginSystem(store=s)
            dependency.installOn(l, s)
            s.checkpoint()
            p = Portal(IRealm(s),
                       [ICredentialsChecker(s)])

            a = l.addAccount(username, 'localhost', SECRET)
            gph = GarbageProtocolHandler(store=a.avatars.open(),
                                         garbage=0)
            dependency.installOn(gph, gph.store)
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


class MemoryUserBaseTest(UserBaseTest):
    """
    Tests for L{axiom.userbase} with an in-memory store.
    @ivar store: The C{Store} object for the items tested.
    """
    def setUp(self):
        """
        Set up for testing with an in-memory store.
        """
        self.store = Store()


class CommandTestCase(unittest.TestCase):
    """
    Integration tests for the 'axiomatic userbase' command.
    """

    def setUp(self):
        self.dbdir = self.mktemp()
        self.store = Store(self.dbdir)


    def tearDown(self):
        self.store.close()


    def _login(self, avatarId, password):
        cc = ICredentialsChecker(self.store)
        p = Portal(IRealm(self.store), [cc])
        return p.login(UsernamePassword(avatarId, password), None,
                       lambda orig, default: orig)


    def assertImplements(self, obj, interface):
        """
        Assert that C{obj} can be adapted to C{interface}.

        @param obj: Any Python object.
        @param interface: A L{zope.interface.Interface} that C{obj} should
        implement.
        """
        self.failUnless(interface.providedBy(interface(obj, None)))


    def userbase(self, *args):
        """
        Run 'axiomatic userbase' with the given arguments on database at
        C{dbdir}.

        @return: A list of lines printed to stdout by the axiomatic command.
        """
        output = StringIO.StringIO()
        sys.stdout, stdout = output, sys.stdout
        try:
            axiomatic.main(['-d', self.dbdir, 'userbase'] + list(args))
        finally:
            sys.stdout = stdout
        return output.getvalue().splitlines()


    def test_install(self):
        """
        Create a database, install userbase and check that the store
        implements L{IRealm} and L{ICredentialsChecker}. i.e. that userbase
        has been installed. This is an integration test.
        """
        self.userbase('install')
        self.assertImplements(self.store, IRealm)
        self.assertImplements(self.store, ICredentialsChecker)


    def test_userCreation(self):
        """
        Create a user on a store, implicitly installing userbase, then try to
        log in with the user. This is an integration test.
        """
        self.userbase('create', 'alice', 'localhost', SECRET)

        def cb((interface, avatar, logout)):
            ss = avatar.avatars.open()
            self.assertEquals(list(userbase.getAccountNames(ss)),
                              [(u'alice', u'localhost')])
            self.assertEquals(avatar.password, SECRET)
            logout()

        d = self._login('alice@localhost', SECRET)
        return d.addCallback(cb)


    def test_listOnClean(self):
        """
        Check that we are given friendly and informative output when we use
        'userbase list' on a fresh store.
        """
        output = self.userbase('list')
        self.assertEquals(output, ['No accounts'])


    def test_list(self):
        """
        When users exist, 'userbase list' should print their IDs one to a
        line.
        """
        self.userbase('create', 'alice', 'localhost', SECRET)
        self.userbase('create', 'bob', 'localhost', SECRET)
        output = self.userbase('list')
        self.assertEquals(output, ['alice@localhost', 'bob@localhost'])


    def test_listWithDisabled(self):
        """
        Check that '[DISABLED]' is printed after the ID of users with disabled
        accounts.
        """
        self.userbase('create', 'alice', 'localhost', SECRET)
        self.userbase('create', 'bob', 'localhost', SECRET)

        def cb((interface, avatar, logout)):
            avatar.disabled = 1
            output = self.userbase('list')
            self.assertEquals(output,
                              ['alice@localhost', 'bob@localhost [DISABLED]'])

        return self._login('bob@localhost', SECRET).addCallback(cb)


    def test_listOffering(self):
        """
        Mantissa offerings are added as users with a 'username' but no domain.
        Check that the 'list' command prints these correctly.
        """
        name = 'offering-name'
        self.userbase('install')
        realm = IRealm(self.store)
        substoreItem = SubStore.createNew(self.store, ('app', name))
        realm.addAccount(name, None, None, internal=True,
                         avatars=substoreItem)
        output = self.userbase('list')
        self.assertEquals(output, [name])



def pvals(m):
    d = m.persistentValues()
    d.pop('account')
    return d


class AccountTestCase(unittest.TestCase):
    def testAccountNames(self):
        dbdir = self.mktemp()
        s = Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        dependency.installOn(ls, s)
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

    def testGetLoginMethods(self):
        """
        Test L{userbase.getLoginMethods}
        """
        dbdir = self.mktemp()
        s = Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        dependency.installOn(ls, s)

        acc = ls.addAccount('username', 'dom.ain', 'password', protocol=u'speech')
        ss = acc.avatars.open()

        for protocol in (None, u'speech'):
            self.assertEquals(list(userbase.getAccountNames(ss, protocol)),
                              [('username', 'dom.ain')])

        # defaults to ANY_PROTOCOL
        acc.addLoginMethod(u'username2', u'dom.ain')

        # check that searching for protocol=speech also gives us the
        # ANY_PROTOCOL LoginMethod
        for protocol in (None, u'speech'):
            self.assertEquals(sorted(userbase.getAccountNames(ss, protocol)),
                              [('username', 'dom.ain'),
                               ('username2', 'dom.ain')])


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
        dependency.installOn(ls, s)
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

    def run():
        pass

class SubStoreMigrationTestCase(unittest.TestCase):

    IMPORTANT_VALUE = 159

    def setUp(self):
        self.dbdir = self.mktemp()
        self.store = Store(self.dbdir)
        self.ls = userbase.LoginSystem(store=self.store)
        self.scheduler = Scheduler(store=self.store)
        dependency.installOn(self.scheduler, self.store)

        self.account = self.ls.addAccount(u'testuser', u'localhost', u'PASSWORD')

        self.accountStore = self.account.avatars.open()

        self.ss = self.accountStore.findOrCreate(SubScheduler)
        dependency.installOn(self.ss, self.accountStore)

        self.origdir = self.accountStore.dbdir
        self.destdir = FilePath(self.mktemp())

    def test_extraction(self):
        """
        Ensure that user store extraction works correctly,
        particularly in the presence of timed events.
        """
        thing = ThingThatMovesAround(store=self.accountStore,
                                     superValue=self.IMPORTANT_VALUE)
        self.ss.schedule(thing, Time() + datetime.timedelta(days=1))
        self.test_noTimedEventsExtraction()
    def test_noTimedEventsExtraction(self):
        """
        Ensure that user store extraction works correctly if no timed
        events are present.
        """
        userbase.extractUserStore(self.account, self.destdir)
        self.assertEquals(
            self.ls.accountByAddress(u'testuser', u'localhost'),
            None)

        self.failIf(list(self.store.query(SubStore, SubStore.storepath == self.origdir)))
        self.origdir.restat(False)
        self.failIf(self.origdir.exists())
        self.failIf(list(self.store.query(_SubSchedulerParentHook)))



    def test_noTimedEventsInsertion(self):
        """
        Test that inserting a user store succeeds if it contains no
        timed events.
        """
        self.test_noTimedEventsExtraction()
        self._testInsertion()

    def test_insertion(self, _deleteDomainDirectory=False):
        """
        Test that inserting a user store succeeds and that the right
        items are placed in the site store as a result.
        """
        self.test_extraction()
        self._testInsertion(_deleteDomainDirectory)
        insertedStore = self.ls.accountByAddress(u'testuser',
                                                 u'localhost').avatars.open()
        self.assertEquals(
            insertedStore.findUnique(ThingThatMovesAround).superValue,
            self.IMPORTANT_VALUE)
        siteStoreSubRef = self.store.getItemByID(insertedStore.idInParent)
        ssph = self.store.findUnique(_SubSchedulerParentHook,
                         _SubSchedulerParentHook.loginAccount == siteStoreSubRef,
                                     default=None)
        self.failUnless(ssph)
        self.failUnless(self.store.findUnique(TimedEvent,
                                              TimedEvent.runnable == ssph))


    def _testInsertion(self, _deleteDomainDirectory=False):
        """
        Helper method for inserting a user store.
        """
        if _deleteDomainDirectory:
            self.store.filesdir.child('account').child('localhost').remove()

        userbase.insertUserStore(self.store, self.destdir)

    def test_insertionWithNoDomainDirectory(self):
        """
        Test that inserting a user store succeeds even if it is the
        first one in that domain to be inserted.
        """
        self.test_insertion(True)


class RealmTestCase(unittest.TestCase):
    """
    Tests for the L{IRealm} implementation in L{axiom.userbase}.
    """
    def setUp(self):
        self.store = Store()
        self.realm = userbase.LoginSystem(store=self.store)
        dependency.installOn(self.realm, self.store)


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
        return self.assertFailure(d, errors.MissingDomainPart)
