
from zope.interface import classProvides

from twisted.python import usage

from twisted import plugin

from axiom import iaxiom, userbase

from xmantissa.website import WebSite

import getpass

class UserBaseCommand(usage.Options):
    classProvides(plugin.IPlugin, iaxiom.IAxiomaticCommand)

    name = 'userbase'
    description = 'Users.  Yay.'

    optParameters = [
        ('username', 'u', None, "The local-part of a user's ID"),
        ('domain', 'd', None, "The domain-part of a user's ID"),
        ('password', 'p', None, "The user's password")]

    def postOptions(self):
        s = self.parent.getStore()
        s.transact(self.doConfiguration, s)

    def doConfiguration(self, s):
        for ls in s.query(userbase.LoginSystem):
            break
        else:
            ls = userbase.LoginSystem(store=s)
            ls.install()
        if self['username'] is not None:
            if not self['domain']:
                raise usage.UsageError(
                    "If you specify a username, you must specify their domain.")
            if not self['password']:
                self['password'] = getpass.getpass('Enter new AXIOM password: ' %())
            ls.addAccount(self['username'],
                          self['domain'],
                          self['password'])


