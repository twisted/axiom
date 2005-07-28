
import sys
import warnings

from twisted import plugin
from twisted.python import usage

from axiom import plugins

from axiom import iaxiom
from axiom.store import Store

class Options(usage.Options):
    optParameters = [
        ('dbdir', 'd', None, 'Path containing axiom database to configure/create'),
        ]

    subCommands = [
        (plg.name, None, plg, plg.description)
        for plg in plugin.getPlugins(iaxiom.IAxiomaticCommand, plugins)
        ]

    store = None

    def getStore(self):
        if self.store is None:
            if self['dbdir'] is None:
                sys.stderr.write(
                    "You are using an in-memory store: this command will likely "
                    "have no effect\n")
            self.store = Store(self['dbdir'])
        return self.store

    def postOptions(self):
        if self.store is not None:
            self.store.close()


def main(argv=None):
    o = Options()
    try:
        o.parseOptions(argv)
    except usage.UsageError, e:
        raise SystemExit(str(e))
