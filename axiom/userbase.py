# Copright 2008 Divmod, Inc.  See LICENSE file for details.
# -*- test-case-name: axiom.test.test_userbase -*-

"""
The L{axiom.userbase} module implements various interfaces from L{twisted.cred}
to allow an Axiom database to serve as an integration point for Twisted
services that do authentication.

While not strictly required, one part of this implementation is the idiom that
Axiom (by default) partitions its user database into a separate data-store for
each users.

This has several advantages:

  - Each user's account can be quickly and independently added to or removed
    from the system; inactive accounts can be quickly moved to archival
    storage.

  - User accounts may be migrated between servers relatively easily.

  - Database queries that deal with a single user's data are completely
    partitioned; even naive and inefficient queries can still be run quickly as
    long as users do not individually have a lot of data in a particular table.

For truly multi-user applications, this partitioning is incomplete without an
abstract facility for exchanging data between different users of the same
application.  This module does not implement such a facility, as it is left to
higher-level mechanisms such as Mantissa's messaging system in
L{xmantissa.messaging}.  However, this module works standalone as well; just be
aware that a user's database contains only their own data.
"""

import warnings
from threading import Thread
import six

from zope.interface import implementer, Interface

from twisted.cred.portal import IRealm
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.checkers import ICredentialsChecker, ANONYMOUS
from twisted.python import log
from twisted.internet.defer import fail
from twisted._threads import pool, createMemoryWorker

from passlib.context import CryptContext
from txpasslib.context import TxCryptContext
from txpasslib.test.doubles import SynchronousReactorThreads

from axiom.store import Store
from axiom.item import Item, declareLegacyItem, empowerment
from axiom.substore import SubStore
from axiom.attributes import (
    text, integer, reference, boolean, AND, OR, inmemory)
from axiom.errors import (
    BadCredentials, NoSuchUser, DuplicateUser, MissingDomainPart)
from axiom.scheduler import IScheduler
from axiom import upgrade, iaxiom

ANY_PROTOCOL = '*'

def dflip(x):
    warnings.warn("Don't use dflip no more", stacklevel=2)
    return x


class AllNamesConflict(Exception):
    """
    When inserting a SubStore into a site store, no names were found which were
    not already associated with an account.

    This prevents the SubStore from being inserted at all.  No files are moved
    and the site database is not modified.
    """


class DatabaseDirectoryConflict(Exception):
    """
    When inserting a SubStore into a site store, the selected ultimate location
    for the SubStore's Axiom database directory already existed.

    This prevents the SubStore from being inserted at all.  No files are moved
    and the site database is not modified.
    """



class IPreauthCredentials(Interface):
    """
    Deprecated.  Don't use this.  If you wrote a checker which can check this
    interface, make it check one of the interfaces L{Preauthenticated}
    implements, instead.
    """



@implementer(IUsernamePassword)
class Preauthenticated(object):
    """
    A credentials object of multiple types which has already been authenticated
    somehow.

    Credentials interfaces methods are implemented to behave as if the correct
    credentials had been supplied.
    """
    def __init__(self, username):
        self.username = username


    def checkPassword(self, password):
        """
        The password checks out.
        """
        return True


    def __repr__(self):
        return '<Preauthenticated: {}>'.format(self.username)



class LoginMethod(Item):
    typeName = 'login_method'
    schemaVersion = 2

    localpart = text(doc="""
    A local-part of my user's identifier.
    """, indexed=True, allowNone=False)

    domain = text(doc="""
    The domain part of my user's identifier. [XXX See TODO below]
    May be None (generally for "system" users).
    """, indexed=True)

    internal = boolean(doc="""
    Flag indicating whether this is a method maintained by this server, or if
    it represents an external contact mechanism (such as a third-party email
    provider)
    """, allowNone=False)

    protocol = text(indexed=True, allowNone=False)
    account = reference(doc="""
    A reference to the LoginAccount for which this is a login method.
    """, allowNone=False)

    verified = boolean(indexed=True, allowNone=False)

def upgradeLoginMethod1To2(old):
    return old.upgradeVersion(
            'login_method', 1, 2,
            localpart=old.localpart,
            domain=old.domain,
            internal=old.internal,
            protocol=old.protocol,
            account=old.account,
            verified=old.verified)

upgrade.registerUpgrader(upgradeLoginMethod1To2, 'login_method', 1, 2)


_globalCC = CryptContext(schemes=['argon2'])


def _daemonThread(*a, **kw):
    """
    Create a L{threading.Thread}, but always set C{daemon}.
    """
    thread = Thread(*a, **kw)
    thread.daemon = True
    return thread


_globalTxCC = None

def _getCC():
    """
    Lazily initialize a global C{TxCryptContext}.
    """
    global _globalTxCC
    if _globalTxCC is None:
        from twisted.internet import reactor
        _globalTxCC = TxCryptContext(
            context=_globalCC,
            reactor=reactor,
            worker=pool(lambda: 10, _daemonThread))
    return _globalTxCC


def getTestContext():
    """
    Construct a C{TxCryptContext} suited for unit tests.

    @rtype: C{Tuple[TxCryptContext, Callable[[], None]]}
    @return: The context, and a callable that will cause one operation to be
        done.
    """
    worker, perform = createMemoryWorker()
    reactor = SynchronousReactorThreads()
    ctx = TxCryptContext(context=_globalCC, reactor=reactor, worker=worker)
    return (ctx, perform)



class LoginAccount(Item):
    """
    I am an entry in a LoginBase.

    @ivar avatars: An Item which is adaptable to various cred client
    interfaces.  Plural because it represents a collection of potentially
    disparate implementors, such as an IResource for web access and an IContact
    for SIP access.

    @ivar disabled: This account has been disabled.  It is still
    database-resident but the user should not be allowed to log in.

    """
    typeName = 'login'
    schemaVersion = 3

    # DEPRECATED: Do not use directly; see setPassword etc.
    password = text()
    passwordHash = text()
    avatars = reference()       # reference to a thing which can be adapted to
                                # implementations for application-level
                                # protocols.  In general this is a reference to
                                # a SubStore because this is optimized for
                                # applications where per-user data is a
                                # substantial portion of the cost.
    disabled = integer()


    def __conform__(self, interface):
        """
        For convenience, forward adaptation to my 'avatars' attribute.
        """
        ifa = interface(self.avatars, None)
        return ifa


    def migrateDown(self):
        """
        Assuming that self.avatars is a SubStore which should contain *only*
        the LoginAccount for the user I represent, remove all LoginAccounts and
        LoginMethods from that store and copy all methods from the site store
        down into it.
        """
        ss = self.avatars.open()
        def _():
            oldAccounts = ss.query(LoginAccount)
            oldMethods = ss.query(LoginMethod)
            for x in list(oldAccounts) + list(oldMethods):
                x.deleteFromStore()
            self.cloneInto(ss, ss)
            IScheduler(ss).migrateDown()
        ss.transact(_)


    def migrateUp(self):
        """
        Copy this LoginAccount and all associated LoginMethods from my store
        (which is assumed to be a SubStore, most likely a user store) into the
        site store which contains it.
        """
        siteStore = self.store.parent
        def _():
            # No convenience method for the following because needing to do it is
            # *rare*.  It *should* be ugly; 99% of the time if you need to do this
            # you're making a mistake. -glyph
            siteStoreSubRef = siteStore.getItemByID(self.store.idInParent)
            self.cloneInto(siteStore, siteStoreSubRef)
            IScheduler(self.store).migrateUp()
        siteStore.transact(_)


    def cloneInto(self, newStore, avatars):
        """
        Create a copy of this LoginAccount and all associated LoginMethods in a different Store.

        Return the copied LoginAccount.
        """
        la = LoginAccount(store=newStore,
                          passwordHash=self.passwordHash,
                          avatars=avatars,
                          disabled=self.disabled)
        for siteMethod in self.store.query(LoginMethod,
                                           LoginMethod.account == self):
            LoginMethod(store=newStore,
                        localpart=siteMethod.localpart,
                        domain=siteMethod.domain,
                        internal=siteMethod.internal,
                        protocol=siteMethod.protocol,
                        verified=siteMethod.verified,
                        account=la)
        return la


    def deleteLoginMethods(self):
        self.store.query(LoginMethod, LoginMethod.account == self).deleteFromStore()


    def addLoginMethod(self, localpart, domain, protocol=ANY_PROTOCOL, verified=False, internal=False):
        """
        Add a login method to this account, propogating up or down as necessary
        to site store or user store to maintain consistency.
        """
        # Out takes you west or something
        if self.store.parent is None:
            # West takes you in
            otherStore = self.avatars.open()
            peer = otherStore.findUnique(LoginAccount)
        else:
            # In takes you east
            otherStore = self.store.parent
            subStoreItem = self.store.parent.getItemByID(self.store.idInParent)
            peer = otherStore.findUnique(LoginAccount,
                                         LoginAccount.avatars == subStoreItem)

        # Up and down take you home
        for store, account in [(otherStore, peer), (self.store, self)]:
            store.findOrCreate(LoginMethod,
                               account=account,
                               localpart=localpart,
                               domain=domain,
                               protocol=protocol,
                               verified=verified,
                               internal=internal)


    def setPassword(self, newPassword):
        """
        Set this account's password unconditionally.

        @param newPassword: The new password.

        @return: A deferred firing when the password has been changed.
        """
        realm = self.store.findUnique(LoginSystem)

        def _hashed(hash):
            # apparently txpasslib gives us bytes hashes on py2, text hashes on
            # py3; let's make those consistent.
            self.passwordHash = hash.decode('ascii') if isinstance(hash, bytes) else hash

        return realm._getCC().hash(newPassword).addCallback(_hashed)


    def replacePassword(self, currentPassword, newPassword):
        """
        Set this account's password if the current password matches.

        @param currentPassword: The password to match against the current one.
        @param newPassword: The new password.

        @return: A deferred firing when the password has been changed.
        @raise BadCredentials: If the current password did not match.
        """

        def _verified(correct):
            if correct:
                return self.setPassword(newPassword)
            else:
                return fail(BadCredentials())

        realm = self.store.findUnique(LoginSystem)
        return (
            realm._getCC()
                .verify(currentPassword, self.passwordHash)
                .addCallback(_verified)
        )


def insertUserStore(siteStore, userStorePath):
    """
    Move the SubStore at the indicated location into the given site store's
    directory and then hook it up to the site store's authentication database.

    @type siteStore: C{Store}
    @type userStorePath: C{FilePath}
    """
    # The following may, but does not need to be in a transaction, because it
    # is merely an attempt to guess a reasonable filesystem name to use for
    # this avatar.  The user store being operated on is expected to be used
    # exclusively by this process.
    ls = siteStore.findUnique(LoginSystem)
    unattachedSubStore = Store(userStorePath)
    for lm in unattachedSubStore.query(LoginMethod,
                                       LoginMethod.account == unattachedSubStore.findUnique(LoginAccount),
                                       sort=LoginMethod.internal.descending):
        if ls.accountByAddress(lm.localpart, lm.domain) is None:
            localpart, domain = lm.localpart, lm.domain
            break
    else:
        raise AllNamesConflict()

    unattachedSubStore.close()

    insertLocation = siteStore.newFilePath('account', domain, localpart + '.axiom')
    insertParentLoc = insertLocation.parent()
    if not insertParentLoc.exists():
        insertParentLoc.makedirs()
    if insertLocation.exists():
        raise DatabaseDirectoryConflict()
    userStorePath.moveTo(insertLocation)
    ss = SubStore(store=siteStore, storepath=insertLocation)
    attachedStore = ss.open()
    # migrateUp() manages its own transactions because it interacts with two
    # different stores.
    attachedStore.findUnique(LoginAccount).migrateUp()


def extractUserStore(userAccount, extractionDestination, legacySiteAuthoritative=True):
    """
    Move the SubStore for the given user account out of the given site store
    completely.  Place the user store's database directory into the given
    destination directory.

    @type userAccount: C{LoginAccount}
    @type extractionDestination: C{FilePath}

    @type legacySiteAuthoritative: C{bool}

    @param legacySiteAuthoritative: before moving the user store, clear its
    authentication information, copy that which is associated with it in the
    site store rather than trusting its own.  Currently this flag is necessary
    (and defaults to true) because things like the ClickChronicle
    password-changer gizmo still operate on the site store.

    """
    if legacySiteAuthoritative:
        # migrateDown() manages its own transactions, since it is copying items
        # between two different stores.
        userAccount.migrateDown()
    av = userAccount.avatars
    av.open().close()
    def _():
        # We're separately deleting several Items from the site store, then
        # we're moving some files.  If we cannot move the files, we don't want
        # to delete the items.

        # There is one unaccounted failure mode here: if the destination of the
        # move is on a different mount point, the moveTo operation will fall
        # back to a non-atomic copy; if all of the copying succeeds, but then
        # part of the deletion of the source files fails, we will be left
        # without a complete store in this site store's files directory, but
        # the account Items will remain.  This will cause odd errors on login
        # and at other unpredictable times.  The database is only one file, so
        # we will either remove it all or none of it.  Resolving this requires
        # manual intervention currently: delete the substore's database
        # directory and the account items (LoginAccount and LoginMethods)
        # manually.

        # However, this failure is extremely unlikely, as it would almost
        # certainly indicate a misconfiguration of the permissions on the site
        # store's files area.  As described above, a failure of the call to
        # os.rename(), if the platform's rename is atomic (which it generally
        # is assumed to be) will not move any files and will cause a revert of
        # the transaction which would have deleted the accompanying items.

        av.deleteFromStore()
        userAccount.deleteLoginMethods()
        userAccount.deleteFromStore()
        av.storepath.moveTo(extractionDestination)
    userAccount.store.transact(_)


def upgradeLoginAccount1To2(oldAccount):
    password = oldAccount.password
    if password is not None:
        try:
            password = six.ensure_str(password)
        except UnicodeDecodeError:
            password = None

    newAccount = oldAccount.upgradeVersion(
        'login', 1, 2,
        password=password,
        avatars=oldAccount.avatars,
        disabled=oldAccount.disabled)

    def make(s, acc):
        LoginMethod(
            store=s,
            localpart=oldAccount.username,
            domain=oldAccount.domain,
            internal=False,
            protocol='email',
            account=acc,
            verified=True)

    make(newAccount.store, newAccount)
    ss = newAccount.avatars.open()
    # create account in substore to represent the user's own record of their
    # password; moves with them during migrations, etc.
    subacc = loginAccountv2(
        store=ss,
        password=newAccount.password,
        avatars=ss,
        disabled=newAccount.disabled)
    make(ss, subacc)

upgrade.registerUpgrader(upgradeLoginAccount1To2, 'login', 1, 2)


loginAccountv2 = declareLegacyItem(
    typeName='login',
    schemaVersion=2,
    attributes=dict(
        avatars=reference(),
        disabled=integer(),
        password=text()))

def upgradeLoginAccount2To3(oldAccount):
    if oldAccount.password is None:
        passwordHash = None
    else:
        passwordHash = six.ensure_str(_globalCC.hash(oldAccount.password))
    return oldAccount.upgradeVersion(
        'login', 2, 3,
        passwordHash=passwordHash,
        avatars=oldAccount.avatars,
        disabled=oldAccount.disabled)

upgrade.registerUpgrader(upgradeLoginAccount2To3, 'login', 2, 3)



class SubStoreLoginMixin:
    def makeAvatars(self, domain, username):
        return SubStore.createNew(self.store, ('account', domain, username + '.axiom'))



@empowerment(IRealm)
@empowerment(ICredentialsChecker)
class LoginBase:
    """
    I am a database powerup which provides an interface to a collection of
    username/password pairs mapped to user application objects.
    """
    credentialInterfaces = (IUsernamePassword,)


    def _getCC(self):
        try:
            return self._txCryptContext
        except AttributeError:
            return _getCC()


    def accountByAddress(self, username, domain):
        """
        @type username: C{unicode} without NUL
        @type domain: C{unicode} without NUL
        """
        for account in self.store.query(LoginAccount,
                                     AND(LoginMethod.domain == domain,
                                         LoginMethod.localpart == username,
                                         LoginAccount.disabled == 0,
                                         LoginMethod.account == LoginAccount.storeID)):
            return account


    def addAccount(self, username, domain, password, avatars=None,
                   protocol='email', disabled=0, internal=False,
                   verified=True):
        """
        Create a user account, add it to this LoginBase, and return it.

        This method must be called within a transaction in my store.

        @param username: the user's name.

        @param domain: the domain part of the user's name [XXX TODO: this
        really ought to say something about whether it's a Q2Q domain, a SIP
        domain, an HTTP realm, or an email address domain - right now the
        assumption is generally that it's an email address domain, but not
        always]

        @param password: A shared secret.

        @param avatars: (Optional).  A SubStore which, if passed, will be used
        by cred as the target of all adaptations for this user.  By default, I
        will create a SubStore, and plugins can be installed on that substore
        using the powerUp method to provide implementations of cred client
        interfaces.

        @raise DuplicateUniqueItem: if the 'avatars' argument already contains
        a LoginAccount.

        @return: an instance of a LoginAccount, with all attributes filled out
        as they are passed in, stored in my store.
        """

        # unicode(None) == u'None', kids.
        if username is not None:
            username = six.ensure_text(username)
        if domain is not None:
            domain = six.ensure_text(domain)
        if password is None:
            passwordHash = None
        else:
            password = six.ensure_text(password)
            passwordHash = six.ensure_str(_globalCC.hash(password))

        if self.accountByAddress(username, domain) is not None:
            raise DuplicateUser(username, domain)
        if avatars is None:
            avatars = self.makeAvatars(domain, username)

        subStore = avatars.open()

        # create this unconditionally; as the docstring says, we must be run
        # within a transaction, so if something goes wrong in the substore
        # transaction this item's creation will be reverted...
        la = LoginAccount(store=self.store,
                          passwordHash=passwordHash,
                          avatars=avatars,
                          disabled=disabled)

        def createSubStoreAccountObjects():

            LoginAccount(store=subStore,
                         passwordHash=passwordHash,
                         disabled=disabled,
                         avatars=subStore)

            la.addLoginMethod(localpart=username,
                              domain=domain,
                              protocol=protocol,
                              internal=internal,
                              verified=verified)

        subStore.transact(createSubStoreAccountObjects)
        return la


    def logoutFactory(self, obj):
        return getattr(obj, 'logout', lambda: None)


    def requestAvatar(self, avatarId, mind, *interfaces):
        if avatarId is ANONYMOUS:
            av = self.store
        else:
            av = self.store.getItemByID(avatarId)
        for interface in interfaces:
            impl = interface(av, None)
            if impl is not None:
                self.loginCount += 1
                log.msg(interface=iaxiom.IStatEvent, name='cred',
                        cred_interface=interface)
                return interface, impl, self.logoutFactory(impl)
        raise NotImplementedError()

    def requestAvatarId(self, credentials):
        def verified(result):
            if result:
                return acct.storeID
            else:
                self.failedLogins += 1
                raise BadCredentials()

        try:
            username, domain = credentials.username.split('@', 1)
        except ValueError:
            self.failedLogins += 1
            raise MissingDomainPart(credentials.username)

        username = six.ensure_text(username)
        domain = six.ensure_text(domain)

        acct = self.accountByAddress(username, domain)
        if acct is not None:
            # Awful hack
            if isinstance(credentials, Preauthenticated):
                return acct.storeID
            else:
                return (
                    self._getCC()
                    .verify(credentials.password, acct.passwordHash)
                    .addCallback(verified))

        self.failedLogins += 1
        raise NoSuchUser(credentials.username)



class LoginSystem(Item, LoginBase, SubStoreLoginMixin):
    schemaVersion = 1
    typeName = 'login_system'

    loginCount = integer(default=0)
    failedLogins = integer(default=0)
    _txCryptContext = inmemory()


def getLoginMethods(store, protocol=None):
    """
    Retrieve L{LoginMethod} items from store C{store}, optionally constraining
    them by protocol
    """
    if protocol is not None:
        comp = OR(LoginMethod.protocol == '*',
                  LoginMethod.protocol == protocol)
    else:
        comp = None
    return store.query(LoginMethod, comp)


def getAccountNames(store, protocol=None):
    """
    Retrieve account name information about the given database.

    @param store: An Axiom Store representing a user account.  It must
    have been opened through the store which contains its account
    information.

    @return: A generator of two-tuples of (username, domain) which
    refer to the given store.
    """
    return ((meth.localpart, meth.domain) for meth
                in getLoginMethods(store, protocol))


def getDomainNames(store):
    """
    Retrieve a list of all local domain names represented in the given store.
    """
    domains = set()
    domains.update(store.query(
            LoginMethod,
            AND(LoginMethod.internal == True,
                LoginMethod.domain != None)).getColumn("domain").distinct())
    return sorted(domains)
