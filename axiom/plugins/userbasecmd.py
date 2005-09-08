
import sys, getpass

from zope.interface import classProvides

from twisted.python import usage
from twisted import plugin

from axiom import iaxiom, attributes, userbase

from xmantissa.website import WebSite

class AxiomaticSubCommandMixin:
    store = property(lambda self: self.parent.store)

    def decodeCommandLine(self, cmdline):
        """Turn a byte string from the command line into a unicode string.
        """
        codec = sys.stdin.encoding or sys.getdefaultencoding()
        return unicode(cmdline, codec)

    def installOn(self, other):
        # XXX check installation on other, not store
        for ls in self.store.query(userbase.LoginSystem):
            raise usage.UsageError("UserBase already installed")
        else:
            ls = userbase.LoginSystem(store=self.store)
            ls.installOn(other)
            return ls

class Install(usage.Options, AxiomaticSubCommandMixin):
    def postOptions(self):
        self.installOn(self.store)

class Create(usage.Options, AxiomaticSubCommandMixin):
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


class Disable(usage.Options, AxiomaticSubCommandMixin):
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


class List(usage.Options, AxiomaticSubCommandMixin):
    def postOptions(self):
        acc = None
        for acc in self.store.query(userbase.LoginAccount):
            print acc.username + '@' + acc.domain,
            if acc.disabled:
                print '[DISABLED]'
            else:
                print
        if acc is None:
            print 'No accounts'
        

class UserBaseCommand(usage.Options):
    classProvides(plugin.IPlugin, iaxiom.IAxiomaticCommand)

    name = 'userbase'
    description = 'Users.  Yay.'

    subCommands = [
        ('install', None, Install, "Install UserBase on an Axiom database"),
        ('create', None, Create, "Create a new user"),
        ('disable', None, Disable, "Disable an existing user"),
        ('list', None, List, "List users in an Axiom database"),
        ]

    store = property(lambda self: self.parent.getStore())
