
"""
Tests for L{axiom.userbase}.
"""

import datetime, io, sys

from zope.interface import Interface, implementer
from zope.interface.verify import verifyObject

from twisted.trial import unittest
from twisted.internet.defer import maybeDeferred

from twisted.cred.portal import Portal, IRealm
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.error import UnauthorizedLogin
from twisted.cred.credentials import (
    IUsernamePassword, IUsernameHashedPassword, UsernamePassword,
    UsernameHashedPassword)

from twisted.python.filepath import FilePath

from epsilon.extime import Time

from axiom.iaxiom import IScheduler
from axiom.store import Store
from axiom.substore import SubStore
from axiom.scheduler import TimedEvent, _SubSchedulerParentHook
from axiom import userbase
from axiom.item import Item
from axiom.attributes import integer
from axiom.scripts import axiomatic
from axiom import errors
from axiom import dependency

class IGarbage(Interface):
    pass

@implementer(IGarbage)
class GarbageProtocolHandler(Item):
    schemaVersion = 1
    typeName = 'test_login_garbage'

    powerupInterfaces = (IGarbage,)
    garbage = integer()

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
        self.store = Store(FilePath(self.mktemp()))


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

        def wasItGph(xxx_todo_changeme):
            (interface, avatar, logout) = xxx_todo_changeme
            self.assertEqual(interface, IGarbage)
            self.assertEqual(avatar, gph)
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
        self.dbdir = FilePath(self.mktemp())
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
        self.assertTrue(interface.providedBy(interface(obj, None)))


    def userbase(self, *args):
        """
        Run 'axiomatic userbase' with the given arguments on database at
        C{dbdir}.

        @return: A list of lines printed to stdout by the axiomatic command.
        """
        output = io.StringIO()
        sys.stdout, stdout = output, sys.stdout
        try:
            axiomatic.main(['-d', self.dbdir.path, 'userbase'] + list(args))
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

        def cb(xxx_todo_changeme1):
            (interface, avatar, logout) = xxx_todo_changeme1
            ss = avatar.avatars.open()
            self.assertEqual(list(userbase.getAccountNames(ss)),
                              [('alice', 'localhost')])
            self.assertEqual(avatar.password, SECRET)
            logout()

        d = self._login('alice@localhost', SECRET)
        return d.addCallback(cb)


    def test_listOnClean(self):
        """
        Check that we are given friendly and informative output when we use
        'userbase list' on a fresh store.
        """
        output = self.userbase('list')
        self.assertEqual(output, ['No accounts'])


    def test_list(self):
        """
        When users exist, 'userbase list' should print their IDs one to a
        line.
        """
        self.userbase('create', 'alice', 'localhost', SECRET)
        self.userbase('create', 'bob', 'localhost', SECRET)
        output = self.userbase('list')
        self.assertEqual(output, ['alice@localhost', 'bob@localhost'])


    def test_listWithDisabled(self):
        """
        Check that '[DISABLED]' is printed after the ID of users with disabled
        accounts.
        """
        self.userbase('create', 'alice', 'localhost', SECRET)
        self.userbase('create', 'bob', 'localhost', SECRET)

        def cb(xxx_todo_changeme2):
            (interface, avatar, logout) = xxx_todo_changeme2
            avatar.disabled = 1
            output = self.userbase('list')
            self.assertEqual(output,
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
        self.assertEqual(output, [name])



def pvals(m):
    d = m.persistentValues()
    d.pop('account')
    return d


class AccountTestCase(unittest.TestCase):
    def testAccountNames(self):
        dbdir = FilePath(self.mktemp())
        s = Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        dependency.installOn(ls, s)
        acc = ls.addAccount('username', 'dom.ain', 'password')
        ss = acc.avatars.open()

        self.assertEqual(
            list(userbase.getAccountNames(ss)),
            [('username', 'dom.ain')])

        acc.addLoginMethod('nameuser', 'ain.dom')

        names = list(userbase.getAccountNames(ss))
        names.sort()
        self.assertEqual(
            names,
            [('nameuser', 'ain.dom'), ('username', 'dom.ain')])

    def testGetLoginMethods(self):
        """
        Test L{userbase.getLoginMethods}
        """
        dbdir = FilePath(self.mktemp())
        s = Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        dependency.installOn(ls, s)

        acc = ls.addAccount('username', 'dom.ain', 'password', protocol='speech')
        ss = acc.avatars.open()

        for protocol in (None, 'speech'):
            self.assertEqual(list(userbase.getAccountNames(ss, protocol)),
                              [('username', 'dom.ain')])

        # defaults to ANY_PROTOCOL
        acc.addLoginMethod('username2', 'dom.ain')

        # check that searching for protocol=speech also gives us the
        # ANY_PROTOCOL LoginMethod
        for protocol in (None, 'speech'):
            self.assertEqual(sorted(userbase.getAccountNames(ss, protocol)),
                              [('username', 'dom.ain'),
                               ('username2', 'dom.ain')])


    def testAvatarStoreState(self):
        """
        You can only pass an 'avatars' argument if it doesn't already have an
        account in it.  Some accounts want to have their stores in slightly odd
        places (like offering.py) but you can't have two accounts added which
        both point to the same store.
        """
        dbdir = FilePath(self.mktemp())
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
        self.assertEqual(acc.avatars.open().query(userbase.LoginAccount).count(), 1)


    def testParallelLoginMethods(self):
        dbdir = FilePath(self.mktemp())
        s = Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        acc = ls.addAccount('username', 'example.com', 'password')
        ss = acc.avatars.open()

        loginMethods = s.query(userbase.LoginMethod)
        subStoreLoginMethods = ss.query(userbase.LoginMethod)

        self.assertEqual(loginMethods.count(), 1)
        self.assertEqual(
            [pvals(m) for m in loginMethods],
            [pvals(m) for m in subStoreLoginMethods])


    def testSiteLoginMethodCreator(self):
        dbdir = FilePath(self.mktemp())
        s = Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        acc = ls.addAccount('username', 'example.com', 'password')

        # Do everything twice to make sure repeated calls don't corrupt state
        # somehow
        for i in [0, 1]:
            acc.addLoginMethod(
                localpart='anothername',
                domain='example.org',
                verified=True,
                protocol='test',
                internal=False)

            loginMethods = s.query(
                userbase.LoginMethod, sort=userbase.LoginMethod.storeID.ascending)

            subStoreLoginMethods = acc.avatars.open().query(
                userbase.LoginMethod, sort=userbase.LoginMethod.storeID.ascending)

            self.assertEqual(loginMethods.count(), 2)

            self.assertEqual(
                [pvals(m) for m in loginMethods],
                [pvals(m) for m in subStoreLoginMethods])


    def testUserLoginMethodCreator(self):
        dbdir = FilePath(self.mktemp())
        s = Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        acc = ls.addAccount('username', 'example.com', 'password')
        ss = acc.avatars.open()
        subStoreLoginAccount = ss.findUnique(userbase.LoginAccount)

        # Do everything twice to make sure repeated calls don't corrupt state
        # somehow
        for i in [0, 1]:
            subStoreLoginAccount.addLoginMethod(
                localpart='anothername',
                domain='example.org',
                verified=True,
                protocol='test',
                internal=False)

            loginMethods = s.query(
                userbase.LoginMethod, sort=userbase.LoginMethod.storeID.ascending)

            subStoreLoginMethods = ss.query(
                userbase.LoginMethod, sort=userbase.LoginMethod.storeID.ascending)

            self.assertEqual(loginMethods.count(), 2)

            self.assertEqual(
                [pvals(m) for m in loginMethods],
                [pvals(m) for m in subStoreLoginMethods])


    def testDomainNames(self):
        s = Store()
        acc = s
        for localpart, domain, internal in [
            ('local', 'example.com', True),
            ('local', 'example.net', True),
            ('remote', 'example.org', False),
            ('another', 'example.com', True),
            ('brokenguy', None, True)]:
            userbase.LoginMethod(
                store=s,
                localpart=localpart,
                domain=domain,
                verified=True,
                account=s,
                protocol='test',
                internal=internal)
        self.assertEqual(userbase.getDomainNames(s), ["example.com", "example.net"])



class ThingThatMovesAround(Item):
    typeName = 'test_thing_that_moves_around'
    schemaVersion = 1

    superValue = integer()

    def run():
        pass

class SubStoreMigrationTestCase(unittest.TestCase):

    IMPORTANT_VALUE = 159

    localpart = 'testuser'
    domain = 'example.com'

    def setUp(self):
        self.dbdir = FilePath(self.mktemp())
        self.store = Store(self.dbdir)
        self.ls = userbase.LoginSystem(store=self.store)
        self.scheduler = IScheduler(self.store)

        self.account = self.ls.addAccount(
            self.localpart, self.domain, 'PASSWORD')

        self.accountStore = self.account.avatars.open()

        self.ss = IScheduler(self.accountStore)

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
        self.assertEqual(
            self.ls.accountByAddress(self.localpart, self.domain),
            None)

        self.assertFalse(list(self.store.query(SubStore, SubStore.storepath == self.origdir)))
        self.origdir.restat(False)
        self.assertFalse(self.origdir.exists())
        self.assertFalse(list(self.store.query(_SubSchedulerParentHook)))


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
        insertedStore = self.ls.accountByAddress(self.localpart,
                                                 self.domain).avatars.open()
        self.assertEqual(
            insertedStore.findUnique(ThingThatMovesAround).superValue,
            self.IMPORTANT_VALUE)
        siteStoreSubRef = self.store.getItemByID(insertedStore.idInParent)
        ssph = self.store.findUnique(_SubSchedulerParentHook,
                         _SubSchedulerParentHook.subStore == siteStoreSubRef,
                                     default=None)
        self.assertTrue(ssph)
        self.assertTrue(self.store.findUnique(TimedEvent,
                                              TimedEvent.runnable == ssph))


    def _testInsertion(self, _deleteDomainDirectory=False):
        """
        Helper method for inserting a user store.
        """
        if _deleteDomainDirectory:
            self.store.filesdir.child('account').child(self.domain).remove()

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
    localpart = 'testuser'
    domain = 'example.com'
    password = 'password'

    def setUp(self):
        self.store = Store()
        self.realm = userbase.LoginSystem(store=self.store)
        dependency.installOn(self.realm, self.store)


    def test_powerup(self):
        """
        Test that L{LoginSystem} powers up the store for L{IRealm}.
        """
        self.assertIdentical(self.realm, IRealm(self.store))


    def _requestAvatarId(self, credentials):
        return maybeDeferred(self.realm.requestAvatarId, credentials)


    def test_requestNonexistentAvatarId(self):
        """
        Test that trying to authenticate as a user who does not exist fails
        with a L{NoSuchUser} exception.
        """
        username = '%s@%s' % (self.localpart, self.domain)
        d = self._requestAvatarId(
            UsernamePassword(username, self.password))
        return self.assertFailure(d, errors.NoSuchUser)


    def test_requestMalformedAvatarId(self):
        """
        Test that trying to authenticate as a user without specifying a
        hostname fails with a L{NoSuchUser} exception.
        """
        d = self._requestAvatarId(
            UsernamePassword(self.localpart, self.password))
        return self.assertFailure(d, errors.MissingDomainPart)


    def test_usernamepassword(self):
        """
        L{LoginSystem.requestAvatarId} returns the store identifier of the
        L{LoginAccount} associated with a L{UsernamePassword} credentials
        object if the username and password identify an existing account.
        """
        account = self.realm.addAccount(
            self.localpart, self.domain, self.password)
        username = '%s@%s' % (self.localpart, self.domain)
        d = self._requestAvatarId(UsernamePassword(username, self.password))
        d.addCallback(self.assertEqual, account.storeID)
        return d


    def test_usernameHashedPasswordDeprecated(self):
        """
        Authenticating with L{twisted.cred.credentials.IUsernameHashedPassword}
        credentials emits a deprecation warning.
        """
        account = self.realm.addAccount(
            self.localpart, self.domain, self.password)
        username = '%s@%s' % (self.localpart, self.domain)
        aid = self.successResultOf(
            self._requestAvatarId(
                UsernameHashedPassword(username, self.password)))
        self.assertEqual(aid, account.storeID)
        ws = self.flushWarnings()
        self.assertEqual(ws[0]['category'], DeprecationWarning)


    def test_usernamepasswordInvalid(self):
        """
        L{LoginSystem.requestAvatarId} fails with L{UnauthorizedLogin} if
        the password supplied with the L{UsernamePassword} credentials is
        not valid for the provided username.
        """
        account = self.realm.addAccount(
            self.localpart, self.domain, self.password)
        username = '%s@%s' % (self.localpart, self.domain)
        d = self._requestAvatarId(UsernamePassword(username, 'blahblah'))
        self.assertFailure(d, UnauthorizedLogin)
        return d


    def test_preauthenticated(self):
        """
        L{LoginSystem.requestAvatarId} returns the store identifier of the
        L{LoginAccount} associated with a L{Preauthenticated} credentials
        object.
        """
        account = self.realm.addAccount(
            self.localpart, self.domain, self.password)
        username = '%s@%s' % (self.localpart, self.domain)
        d = self._requestAvatarId(userbase.Preauthenticated(username))
        d.addCallback(self.assertEqual, account.storeID)
        return d


    def test_setPassword(self):
        """
        L{LoginAccount.setPassword} allows for logging in with the new password
        and not the old.
        """
        account = self.realm.addAccount(
            self.localpart, self.domain, self.password)
        username = '%s@%s' % (self.localpart, self.domain)
        self.successResultOf(account.setPassword('blahblah'))
        self.assertEqual(
            self.successResultOf(
                self._requestAvatarId(
                    UsernamePassword(username, 'blahblah'))),
            account.storeID)
        self.failureResultOf(
            self._requestAvatarId(
                UsernamePassword(username, self.password)),
            UnauthorizedLogin)


    def test_replacePasswordWrong(self):
        """
        L{LoginAccount.replacePassword} fails with L{BadCredentials} if an
        incorrect current password is supplied.
        """
        account = self.realm.addAccount(
            self.localpart, self.domain, self.password)
        self.failureResultOf(
            account.replacePassword('blahblah', 'blah'),
            errors.BadCredentials)


    def test_replacePasswordCorrect(self):
        """
        L{LoginAccount.replacePassword} allows for logging in with the new
        password and not the old if the correct current password is supplied.
        """
        account = self.realm.addAccount(
            self.localpart, self.domain, self.password)
        username = '%s@%s' % (self.localpart, self.domain)
        self.successResultOf(
            account.replacePassword(self.password, 'blahblah'))
        self.assertEqual(
            self.successResultOf(
                self._requestAvatarId(
                    UsernamePassword(username, 'blahblah'))),
            account.storeID)
        self.failureResultOf(
            self._requestAvatarId(
                UsernamePassword(username, self.password)),
            UnauthorizedLogin)



class PreauthenticatedTests(unittest.TestCase):
    """
    Tests for L{userbase.Preauthenticated}.
    """
    def test_repr(self):
        """
        L{userbase.Preauthenticated} has a repr which identifies its type and
        its user.
        """
        self.assertEqual(
            repr(userbase.Preauthenticated('foo@bar')),
            '<Preauthenticated: foo@bar>')


    def test_usernamepassword(self):
        """
        L{Preauthenticated} implements L{IUsernamePassword} and succeeds all
        authentication checks.
        """
        creds = userbase.Preauthenticated('foo@bar')
        self.assertTrue(
            verifyObject(IUsernamePassword, creds),
            "Preauthenticated does not implement IUsernamePassword")
        self.assertTrue(
            creds.checkPassword('random string'),
            "Preauthenticated did not accept an arbitrary password.")


    def test_usernamehashedpassword(self):
        """
        L{Preauthenticated} implements L{IUsernameHashedPassword} and succeeds
        all authentication checks.
        """
        creds = userbase.Preauthenticated('foo@bar')
        self.assertTrue(
            verifyObject(IUsernameHashedPassword, creds),
            "Preauthenticated does not implement IUsernameHashedPassword")
        self.assertTrue(
            creds.checkPassword('arbitrary bytes'),
            "Preauthenticated did not accept an arbitrary password.")
