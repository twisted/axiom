# -*- test-case-name: axiom.test.test_userbase -*-

from twisted.cred.portal import IRealm
from twisted.cred.credentials import IUsernamePassword, IUsernameHashedPassword
from twisted.cred.checkers import ICredentialsChecker, ANONYMOUS
from twisted.cred.error import UnauthorizedLogin
from twisted.python import log

from axiom.substore import SubStore
from axiom.item import Item
from axiom.attributes import text, bytes, integer, reference, AND

from zope.interface import implements, Interface

def dflip(x):
    l = x.split('.')
    l.reverse()
    return '.'.join(l)

class BadCredentials(UnauthorizedLogin):
    pass

class NoSuchUser(UnauthorizedLogin):
    pass

class DuplicateUser(Exception):
    pass



class LoginAccount(Item):
    schemaVersion = 1
    typeName = 'login'

    username = text(indexed=True)
    domain = text(indexed=True) # flipped using dflip, e.g. "com.divmod"
    password = bytes()
    avatars = reference()       # reference to a thing which can be adapted to
                                # implementations for application-level
                                # protocols.  In general this is a reference to
                                # a SubStore because this is optimized for
                                # applications where per-user data is a
                                # substantial portion of the cost.
    disabled = integer()

    def __conform__(self, interface):
        return interface(self.avatars, None)

class LoginSystem(Item):
    implements(IRealm, ICredentialsChecker)

    credentialInterfaces = (IUsernamePassword, IUsernameHashedPassword)

    schemaVersion = 1
    typeName = 'login_system'

    loginCount = integer()
    failedLogins = integer()

    def __init__(self, **kw):
        super(LoginSystem, self).__init__(**kw)
        self.failedLogins = 0
        self.loginCount = 0

    def install(self):
        self.store.powerUp(self, IRealm)
        self.store.powerUp(self, ICredentialsChecker)

    def accountByAddress(self, username, domain):
        """
        @type username: C{unicode} without NUL
        @type domain: C{unicode} without NUL
        """
        for account in self.store.query(LoginAccount,
                                     AND(LoginAccount.domain == dflip(domain),
                                         LoginAccount.username == username)):
            return account

    def addAccount(self, username, domain, password):
        username = unicode(username)
        domain = unicode(domain)
        if self.accountByAddress(username, domain) is not None:
            raise DuplicateUser(username, domain)
        return LoginAccount(store=self.store,
                            username=username,
                            domain=dflip(domain),
                            password=password,
                            avatars=SubStore(self.store,
                                             ('account', domain, username)),
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
        username, domain = credentials.username.split('@', 1)

        username = unicode(username)
        domain = unicode(domain)

        acct = self.accountByAddress(username, domain)
        if acct is not None:
            password = acct.password
            if credentials.checkPassword(password):
                return acct.storeID
            else:
                self.failedLogins += 1
                raise BadCredentials()
        raise NoSuchUser()

