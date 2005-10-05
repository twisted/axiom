# -*- test-case-name: axiom.test.test_userbase -*-

import warnings

from twisted.cred.portal import IRealm
from twisted.cred.credentials import IUsernamePassword, IUsernameHashedPassword
from twisted.cred.checkers import ICredentialsChecker, ANONYMOUS
from twisted.cred.error import UnauthorizedLogin
from twisted.python import log

from axiom.substore import SubStore
from axiom.item import Item
from axiom.attributes import text, bytes, integer, reference, AND
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


class LoginAccount(Item):
    schemaVersion = 1
    typeName = 'login'

    username = text(indexed=True)
    domain = text(indexed=True)
    password = bytes()
    avatars = reference()       # reference to a thing which can be adapted to
                                # implementations for application-level
                                # protocols.  In general this is a reference to
                                # a SubStore because this is optimized for
                                # applications where per-user data is a
                                # substantial portion of the cost.
    disabled = integer()

    def __conform__(self, interface):
        ifa = interface(self.avatars, None)
        return ifa

class SubStoreLoginMixin:
    def makeAvatars(self, domain, username):
        return SubStore(self.store, ('account', domain, username))

class LoginBase:
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
                                     AND(LoginAccount.domain == domain,
                                         LoginAccount.username == username)):
            return account

    def addAccount(self, username, domain, password, avatars=None):
        username = unicode(username)
        domain = unicode(domain)
        if self.accountByAddress(username, domain) is not None:
            raise DuplicateUser(username, domain)
        if avatars is None:
            avatars = self.makeAvatars(domain, username)
        return LoginAccount(store=self.store,
                            username=username,
                            domain=domain,
                            password=password,
                            avatars=avatars,
                            disabled=0)

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
    for acc in store.parent.query(LoginAccount, LoginAccount.avatars == subStore):
        yield (acc.username, acc.domain)
