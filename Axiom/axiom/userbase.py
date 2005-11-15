# -*- test-case-name: axiom.test.test_userbase -*-

import warnings

from twisted.cred.portal import IRealm
from twisted.cred.credentials import IUsernamePassword, IUsernameHashedPassword
from twisted.cred.checkers import ICredentialsChecker, ANONYMOUS

from axiom.substore import SubStore
from axiom.item import Item
from axiom.attributes import text, integer, reference, boolean, AND
from axiom.errors import BadCredentials, NoSuchUser, DuplicateUser

from zope.interface import implements, Interface, Attribute

def dflip(x):
    warnings.warn("Don't use dflip no more", stacklevel=2)
    return x

class IPreauthCredentials(Interface):
    """
    Credentials used to indicate the user has indeed authenticated
    already, even though we have no credentials to present at the moment.
    """
    username = Attribute("username@domain-style string")


class Preauthenticated(object):
    implements(IPreauthCredentials)

    def __init__(self, username):
        self.username = username

    def checkPassword(self, password):
        # XXX should we really be implementing this here?  hmm.  sip tests
        # require it but it seems wrong.
        return True


class LoginMethod(Item):
    typeName = 'login_method'
    schemaVersion = 1

    localpart = text(doc="""
    A local-part of my user's identifier.
    """, indexed=True, allowNone=False)

    domain = text(doc="""
    The domain part of my user's identifier. [XXX See TODO below]
    """, indexed=True, allowNone=False)

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
    schemaVersion = 2

    password = text()
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

def upgradeLoginAccount1To2(oldAccount):
    newAccount = oldAccount.upgradeVersion(
        'login', 1, 2,
        password=oldAccount.password.decode('ascii'),
        avatars=oldAccount.avatars,
        disabled=oldAccount.disabled)

    def make(s, acc):
        LoginMethod(
            store=s,
            localpart=oldAccount.username,
            domain=oldAccount.domain,
            internal=False,
            protocol=u'email',
            account=acc,
            verified=True)

    make(newAccount.store, newAccount)
    ss = newAccount.avatars.open()
    # create account in substore to represent the user's own record of their
    # password; moves with them during migrations, etc.
    subacc = LoginAccount(store=ss,
                          password=newAccount.password,
                          avatars=ss,
                          disabled=newAccount.disabled)
    make(ss, subacc)

from axiom import upgrade
upgrade.registerUpgrader(upgradeLoginAccount1To2, 'login', 1, 2)


class SubStoreLoginMixin:
    def makeAvatars(self, domain, username):
        return SubStore(self.store, ('account', domain, username))

class LoginBase:
    """
    I am a database powerup which provides an interface to a collection of
    username/password pairs mapped to user application objects.
    """
    implements(IRealm, ICredentialsChecker)

    credentialInterfaces = (IUsernamePassword, IUsernameHashedPassword, IPreauthCredentials)

    def installOn(self, other):
        other.powerUp(self, IRealm)
        other.powerUp(self, ICredentialsChecker)

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
                   protocol=u'email', disabled=0, internal=False,
                   verified=True):
        """
        Create a user account, add it to this LoginBase, and return it.

        @param username: the user's name.

        @param domain: the domain part of the user's name [XXX TODO: this
        really ought to say something about whether it's a Q2Q domain, a SIP
        domain, an HTTP realm, or an email address domain - right now the
        assumption is generally that it's an email address domain, but not
        always]

        @param password: A shared secret.

        @param avatars: (Optional).  An object which, if passed, will be used
        by cred as the target of all adaptations for this user.  By default, I
        will create a SubStore, and plugins can be installed on that substore
        using the powerUp method to provide implementations of cred client
        interfaces.

        @return: an instance of a LoginAccount, with all attributes filled out
        as they are passed in, stored in my store.
        """
        username = unicode(username)
        domain = unicode(domain)
        password = unicode(password)
        if self.accountByAddress(username, domain) is not None:
            raise DuplicateUser(username, domain)
        if avatars is None:
            avatars = self.makeAvatars(domain, username)
        la = LoginAccount(store=self.store,
                          password=password,
                          avatars=avatars,
                          disabled=disabled)

        lm = LoginMethod(store=self.store,
                         localpart=username,
                         domain=domain,
                         protocol=protocol,
                         internal=internal,
                         verified=verified,
                         account=la)

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
                return interface, impl, self.logoutFactory(impl)
        raise NotImplementedError()

    def requestAvatarId(self, credentials):
        passwordSecure = IUsernameHashedPassword(credentials, None) is not None
        # ^ need to do something with this.  security warning perhaps?

        try:
            username, domain = credentials.username.split('@', 1)
            username = unicode(username)
            domain = unicode(domain)

            acct = self.accountByAddress(username, domain)
            if acct is not None:
                if IPreauthCredentials.providedBy(credentials):
                    return acct.storeID
                else:
                    password = acct.password
                    if credentials.checkPassword(password):
                        return acct.storeID
                    else:
                        raise BadCredentials()
            raise NoSuchUser(credentials.username)
        except:
            self.failedLogins += 1
            raise

class LoginSystem(Item, LoginBase, SubStoreLoginMixin):
    schemaVersion = 1
    typeName = 'login_system'

    loginCount = integer(default=0)
    failedLogins = integer(default=0)


def getAccountNames(store):
    """
    Retrieve account name information about the given database.

    @param store: An Axiom Store representing a user account.  It must
    have been opened through the store which contains its account
    information.

    @return: A generator of two-tuples of (username, domain) which
    refer to the given store.
    """
    if store.parent is None:
        raise ValueError("Orphan store has no account names")
    subStore = store.parent.getItemByID(store.idInParent)
    for meth in store.parent.query(LoginMethod,
                                   AND(LoginAccount.avatars == subStore,
                                       LoginMethod.account == LoginAccount.storeID)):
        yield (meth.localpart, meth.domain)
