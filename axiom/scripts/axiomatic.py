# -*- test-case-name: axiomatic.test.test_axiomatic -*-
from __future__ import print_function
from zope.interface import alsoProvides, noLongerProvides

import os
import sys
import glob
import errno
import signal
import six

from twisted.plugin import IPlugin, getPlugins
from twisted.python import usage
from twisted.python.runtime import platform
from twisted.scripts import twistd

from axiom.iaxiom import IAxiomaticCommand
from six.moves import input
import six

class AxiomaticSubCommandMixin(object):
    store = property(lambda self: self.parent.getStore())

    def decodeCommandLine(self, cmdline):
        """
        Turn whatever type the command line was (possibly text in py3, possibly
        bytes in py2) into a text string.
        """
        if isinstance(cmdline, six.text_type):
            return cmdline
        codec = getattr(sys.stdin, 'encoding', None) or sys.getdefaultencoding()
        return six.text_type(cmdline, codec)



class _AxiomaticCommandMeta(type):
    """
    Metaclass for L{AxiomaticCommand}.

    This serves to make subclasses provide L{IPlugin} and L{IAxiomaticCommand}.
    """
    def __new__(cls, name, bases, attrs):
        newcls = type.__new__(cls, name, bases, attrs)
        alsoProvides(newcls, IPlugin, IAxiomaticCommand)
        return newcls



class AxiomaticSubCommand(usage.Options, AxiomaticSubCommandMixin):
    """
    L{twisted.python.usage.Options} subclass for Axiomatic sub commands.
    """



class AxiomaticCommand(six.with_metaclass(_AxiomaticCommandMeta, usage.Options, AxiomaticSubCommandMixin)):
    """
    L{twisted.python.usage.Options} subclass for Axiomatic plugin commands.

    Subclass this to have your class automatically provide the necessary
    interfaces to be picked up by axiomatic.
    """

noLongerProvides(AxiomaticCommand, IPlugin)
noLongerProvides(AxiomaticCommand, IAxiomaticCommand)



class PIDMixin:

    def _sendSignal(self, signal):
        if platform.isWindows():
            raise usage.UsageError("You can't send signals on Windows (XXX TODO)")
        dbdir = self.parent.getStoreDirectory()
        serverpid = int(file(os.path.join(dbdir, 'run', 'axiomatic.pid')).read())
        os.kill(serverpid, signal)
        return serverpid

    def signalServer(self, signal):
        try:
            return self._sendSignal(signal)
        except (OSError, IOError) as e:
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
        print('A server is running from the Axiom database %r, PID %d.' % (dbdir, serverpid))



class Start(twistd.ServerOptions):
    run = staticmethod(twistd.run)

    @property
    def subCommands(self):
        raise AttributeError()


    def getArguments(self, store, args):
        run = store.dbdir.child("run")
        logs = run.child("logs")
        handleLogfile = True
        handlePidfile = True

        for arg in args:
            if arg.startswith("--logfile=") or arg in (
                "-l", "--logfile", "-n", "--nodaemon"
            ):
                handleLogfile = False
            elif arg.startswith("--pidfile=") or arg == "--pidfile":
                handlePidfile = False

        if handleLogfile:
            if not logs.exists():
                logs.makedirs()
            args.extend(["--logfile", logs.child("axiomatic.log").path])

        if not platform.isWindows() and handlePidfile:
            args.extend(["--pidfile", run.child("axiomatic.pid").path])
        args.extend(["axiomatic-start", "--dbdir", store.dbdir.path])
        if store.journalMode is not None:
            args.extend(['--journal-mode', store.journalMode.encode('ascii')])
        return args


    def parseOptions(self, args):
        if "--help" in args:
            self.opt_help()
        else:
            # If a reactor is being selected, it must be done before the store
            # is opened, since that may execute arbitrary application code
            # which may in turn install the default reactor.
            for index, arg in enumerate(args):
                if arg in ("--reactor", "-r"):
                    shortName = args[index + 1]
                    del args[index:index + 2]
                    self.opt_reactor(shortName)
                    break
                elif arg.startswith("--reactor="):
                    shortName = arg.split("=")[1]
                    del args[index]
                    self.opt_reactor(shortName)
                    break
            sys.argv[1:] = self.getArguments(self.parent.getStore(), args)
            self.run()



class Options(usage.Options):
    def subCommands():
        def get(self):
            yield ('start', None, Start, 'Launch the given Axiom database')
            if not platform.isWindows():
                yield ('stop', None, Stop, 'Stop the server running from the given Axiom database')
                yield ('status', None, Status, 'Report whether a server is running from the given Axiom database')

            from axiom import plugins
            for plg in getPlugins(IAxiomaticCommand, plugins):
                try:
                    yield (plg.name, None, plg, plg.description)
                except AttributeError:
                    raise RuntimeError("Maldefined plugin: %r" % (plg,))
        return get,
    subCommands = property(*subCommands())

    optParameters = [
        ('dbdir', 'd', None, 'Path containing axiom database to configure/create'),
        ('journal-mode', None, None, 'SQLite journal mode to set'),
        ]

    optFlags = [
        ('debug', 'b', 'Enable Axiom-level debug logging')]

    store = None

    def usedb(self, potentialdb):
        yn = input("Use database %r? (Y/n) " % (potentialdb,))
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
        jm = self['journal-mode']
        if jm is not None:
            jm = six.ensure_str(jm)
        if self.store is None:
            self.store = Store(
                self.getStoreDirectory(), debug=self['debug'], journalMode=jm)
        return self.store


    def postOptions(self):
        if self.store is not None:
            self.store.close()


def main(argv=None):
    o = Options()
    try:
        o.parseOptions(argv)
    except usage.UsageError as e:
        raise SystemExit(str(e))
