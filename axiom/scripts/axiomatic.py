# -*- test-case-name: axiomatic.test.test_axiomatic -*-
from zope.interface import directlyProvides

import os
import sys
import glob
import errno
import signal

from twisted import plugin
from twisted.python import usage
from twisted.python.runtime import platform
from twisted.scripts import twistd

from axiom import iaxiom

class AxiomaticSubCommandMixin(object):
    store = property(lambda self: self.parent.getStore())

    def decodeCommandLine(self, cmdline):
        """Turn a byte string from the command line into a unicode string.
        """
        codec = getattr(sys.stdin, 'encoding', None) or sys.getdefaultencoding()
        return unicode(cmdline, codec)

class _metaASC(type):
    def __new__(cls, name, bases, attrs):
        newcls = type.__new__(cls, name, bases, attrs)
        if not (newcls.__name__ == 'AxiomaticCommand' and newcls.__module__ == _metaASC.__module__):
            directlyProvides(newcls, plugin.IPlugin, iaxiom.IAxiomaticCommand)
        return newcls

class AxiomaticSubCommand(usage.Options, AxiomaticSubCommandMixin):
    pass

class AxiomaticCommand(usage.Options, AxiomaticSubCommandMixin):
    __metaclass__ = _metaASC



class PIDMixin:

    def _sendSignal(self, signal):
        if platform.isWinNT():
            raise usage.UsageError("You can't send signals on Windows (XXX TODO)")
        dbdir = self.parent.getStoreDirectory()
        serverpid = int(file(os.path.join(dbdir, 'run', 'axiomatic.pid')).read())
        os.kill(serverpid, signal)
        return serverpid

    def signalServer(self, signal):
        try:
            return self._sendSignal(signal)
        except (OSError, IOError), e:
            if e.errno in (errno.ENOENT, errno.ESRCH):
                raise usage.UsageError('There is no server running from the Axiom database %r.' % (self.parent.getStoreDirectory(),))
            else:
                raise


class Stop(usage.Options, PIDMixin):
    def postOptions(self):
        self.signalServer(signal.SIGINT)



class Status(usage.Options, PIDMixin):
    def postOptions(self):
        dbdir = self.parent.getStoreDirectory()
        serverpid = self.signalServer(0)
        print 'A server is running from the Axiom database %r, PID %d.' % (dbdir, serverpid)



class Start(twistd.ServerOptions):
    run = staticmethod(twistd.run)

    def subCommands():
        raise AttributeError()
    subCommands = property(subCommands)


    def getArguments(self, store, args):
        run = store.dbdir.child("run")
        logs = run.child("logs")
        if "--logfile" not in args and "-l" not in args and "--nodaemon" not in args and "-n" not in args:
            if not logs.exists():
                logs.makedirs()
            args.extend(["--logfile", logs.child("axiomatic.log").path])
        if not platform.isWindows() and "--pidfile" not in args:
            args.extend(["--pidfile", run.child("axiomatic.pid").path])
        args.extend(["axiomatic-start", "--dbdir", store.dbdir.path])
        return args


    def parseOptions(self, args):
        if "--help" in args:
            self.opt_help()
        else:
            # If a reactor is being selected, it must be done before the store
            # is opened, since that may execute arbitrary application code
            # which may in turn install the default reactor.
            if "--reactor" in args:
                reactorIndex = args.index("--reactor")
                shortName = args[reactorIndex + 1]
                del args[reactorIndex:reactorIndex + 2]
                self.opt_reactor(shortName)
            sys.argv[1:] = self.getArguments(self.parent.getStore(), args)
            self.run()



class Options(usage.Options):
    def subCommands():
        def get(self):
            yield ('start', None, Start, 'Launch the given Axiom database')
            if not platform.isWinNT():
                yield ('stop', None, Stop, 'Stop the server running from the given Axiom database')
                yield ('status', None, Status, 'Report whether a server is running from the given Axiom database')

            from axiom import plugins
            for plg in plugin.getPlugins(iaxiom.IAxiomaticCommand, plugins):
                try:
                    yield (plg.name, None, plg, plg.description)
                except AttributeError:
                    raise RuntimeError("Maldefined plugin: %r" % (plg,))
        return get,
    subCommands = property(*subCommands())

    optParameters = [
        ('dbdir', 'd', None, 'Path containing axiom database to configure/create'),
        ]

    optFlags = [
        ('debug', 'b', 'Enable Axiom-level debug logging')]

    store = None

    def usedb(self, potentialdb):
        yn = raw_input("Use database %r? (Y/n) " % (potentialdb,))
        if yn.lower() in ('y', 'yes', ''):
            self['dbdir'] = potentialdb
        else:
            raise usage.UsageError('Select another database with the -d option, then.')

    def getStoreDirectory(self):
        if self['dbdir'] is None:
            possibilities = glob.glob('*.axiom')
            if len(possibilities) > 1:
                raise usage.UsageError(
                    "Multiple databases found here, please select one with "
                    "the -d option: %s" % (' '.join(possibilities),))
            elif len(possibilities) == 1:
                self.usedb(possibilities[0])
            else:
                self.usedb(self.subCommand + '.axiom')
        return self['dbdir']

    def getStore(self):
        from axiom.store import Store
        if self.store is None:
            self.store = Store(self.getStoreDirectory(), debug=self['debug'])
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
