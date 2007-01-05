
from epsilon.hotfix import require
require('twisted', 'filepath_copyTo')

import getpass

from twisted.python import usage
from twisted.python import filepath

from axiom import attributes, userbase, dependency
from axiom.scripts import axiomatic

class UserbaseMixin:
    def installOn(self, other):
        # XXX check installation on other, not store
        for ls in self.store.query(userbase.LoginSystem):
            raise usage.UsageError("UserBase already installed")
        else:
            ls = userbase.LoginSystem(store=self.store)
            dependency.installOn(ls, other)
            return ls

class Install(axiomatic.AxiomaticSubCommand, UserbaseMixin):
    def postOptions(self):
        self.installOn(self.store)

class Create(axiomatic.AxiomaticSubCommand, UserbaseMixin):
    synopsis = "<username> <domain> [password]"

    def parseArgs(self, username, domain, password=None):
        self['username'] = self.decodeCommandLine(username)
        self['domain'] = self.decodeCommandLine(domain)
        self['password'] = password

    def postOptions(self):
        for ls in self.store.query(userbase.LoginSystem):
            break
        else:
            ls = self.installOn(self.store)

        msg = 'Enter new AXIOM password: '
        while not self['password']:
            password = getpass.getpass(msg)
            second = getpass.getpass('Repeat to verify: ')
            if password == second:
                self['password'] = password
            else:
                msg = 'Passwords do not match.  Enter new AXIOM password: '

        try:
            acc = ls.addAccount(self['username'],
                                self['domain'],
                                self['password'])
        except userbase.DuplicateUser:
            raise usage.UsageError("An account by that name already exists.")


class Disable(axiomatic.AxiomaticSubCommand):
    synopsis = "<username> <domain>"

    def parseArgs(self, username, domain):
        self['username'] = self.decodeCommandLine(username)
        self['domain'] = self.decodeCommandLine(domain)

    def postOptions(self):
        for acc in self.store.query(userbase.LoginAccount,
                                    attributes.AND(userbase.LoginAccount.username == self['username'],
                                                   userbase.LoginAccount.domain == self['domain'])):
            if acc.disabled:
                raise usage.UsageError("That account is already disabled.")
            else:
                acc.disabled = True
                break
        else:
            raise usage.UsageError("No account by that name exists.")


class List(axiomatic.AxiomaticSubCommand):
    def postOptions(self):
        acc = None
        for acc in self.store.query(userbase.LoginMethod):
            if acc.domain is None:
                print acc.localpart,
            else:
                print acc.localpart + '@' + acc.domain,
            if acc.account.disabled:
                print '[DISABLED]'
            else:
                print
        if acc is None:
            print 'No accounts'


class UserBaseCommand(axiomatic.AxiomaticCommand):
    name = 'userbase'
    description = 'LoginSystem introspection and manipulation.'

    subCommands = [
        ('install', None, Install, "Install UserBase on an Axiom database"),
        ('create', None, Create, "Create a new user"),
        ('disable', None, Disable, "Disable an existing user"),
        ('list', None, List, "List users in an Axiom database"),
        ]

    def getStore(self):
        return self.parent.getStore()


class Extract(axiomatic.AxiomaticCommand):
    name = 'extract-user'
    description = 'Remove an account from the login system, moving its associated database to the filesystem.'
    optParameters = [
        ('address', 'a', None, 'localpart@domain-format identifier of the user store to extract.'),
        ('destination', 'd', None, 'Directory into which to extract the user store.')]

    def extractSubStore(self, localpart, domain, destinationPath):
        siteStore = self.parent.getStore()
        la = siteStore.findFirst(
            userbase.LoginMethod,
            attributes.AND(userbase.LoginMethod.localpart == localpart,
                           userbase.LoginMethod.domain == domain)).account
        userbase.extractUserStore(la, destinationPath)

    def postOptions(self):
        localpart, domain = self.decodeCommandLine(self['address']).split('@', 1)
        destinationPath = filepath.FilePath(
            self.decodeCommandLine(self['destination'])).child(localpart + '@' + domain + '.axiom')
        self.extractSubStore(localpart, domain, destinationPath)

class Insert(axiomatic.AxiomaticCommand):
    name = 'insert-user'
    description = 'Insert a user store, such as one extracted with "extract-user", into a site store and login system.'
    optParameters = [
        ('userstore', 'u', None, 'Path to user store to be inserted.')
        ]

    def postOptions(self):
        userbase.insertUserStore(self.parent.getStore(),
                                 filepath.FilePath(self.decodeCommandLine(self['userstore'])))
