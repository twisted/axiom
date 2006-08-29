from zope.interface import directlyProvides

import os
import sys
import glob
import errno
import signal

from twisted import plugin
from twisted.python import usage, log
from twisted.python.runtime import platform
from twisted.application import app, service

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
        directlyProvides(newcls, plugin.IPlugin, iaxiom.IAxiomaticCommand)
        return newcls

class AxiomaticSubCommand(usage.Options, AxiomaticSubCommandMixin):
    pass

class AxiomaticCommand(usage.Options, AxiomaticSubCommandMixin):
    __metaclass__ = _metaASC

# The following should REALLY be taken care of by Twisted itself.
if platform.isWinNT():
    from twisted.scripts import _twistw as twistd
else:
    try:
        from twisted.scripts import _twistd_unix as twistd
    except ImportError:
        from twisted.scripts import twistd

class Start(twistd.ServerOptions):
    def noSubCommands(self):
        raise AttributeError()
    subCommands = property(noSubCommands)

    def _fixConfig(self):
        self['no_save'] = True
        self['nodaemon'] = self['nodaemon'] or self['debug']

        dbdir = self.parent.getStoreDirectory()

        rundir = os.path.join(dbdir, 'run')
        if not os.path.exists(rundir):
            os.mkdir(rundir)

        if self['logfile'] is None and not self['nodaemon']:
            logdir = os.path.join(rundir, 'logs')
            if not os.path.exists(logdir):
                os.mkdir(logdir)
            self['logfile'] = os.path.join(logdir, 'axiomatic.log')

        if platform.isWinNT():
            # We're done; no pidfile support.
            return
        if self['pidfile'] == 'twistd.pid':
            self['pidfile'] = os.path.join(rundir, 'axiomatic.pid')
        elif self['pidfile']:
            self['pidfile'] = os.path.abspath(self['pidfile'])

    def _constructApplication(self):
        application = service.Application("Axiom Service")
        service.IService(self.parent.getStore()).setServiceParent(application)
        return application


    def postOptions(self):
        if platform.isWinNT():
            self._win32PostOptions()
        else:
            self._unixPostOptions()

    def _checkPID(self):
        # There *IS* a Windows way to do this, but it doesn't use PIDs.
        if not platform.isWinNT():
            twistd.checkPID(self['pidfile'])

    def _removePID(self):
        if not platform.isWinNT():
            twistd.removePID(self['pidfile'])

    def _startApplication(self):
        if not platform.isWinNT():
            twistd.startApplication(self, self.application)
        else:
            service.IService(self.application).privilegedStartService()
            app.startApplication(self.application, False)

    def _startLogging(self):
        if not platform.isWinNT():
            twistd.startLogging(
                self['logfile'],
                self['syslog'],
                self['prefix'],
                self['nodaemon'])
        else:
            twistd.startLogging('-') # self['logfile']

    def postOptions(self):

        # This does not invoke the super implementation.  At the time this
        # method was implemented, all the super method did was *conditionally*
        # set self['no_save'] to True and take the abspath of self['pidfile'].
        # See below for the irrelevance of those operations.

        app.installReactor(self['reactor'])

        self._fixConfig()
        self._checkPID()

        S = self.parent.getStore()  # make sure we open it here

        oldstdout = sys.stdout
        oldstderr = sys.stderr

        self._startLogging()
        app.initialLog()

        self.application = application = self._constructApplication()
        self._startApplication()
        app.runReactorWithLogging(self, oldstdout, oldstderr)
        self._removePID()
        app.reportProfile(
            self['report-profile'],
            service.IProcess(application).processName)
        log.msg("Server Shut Down.")


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
        dbdir = self.parent.getStoreDirectory()
        self.signalServer(signal.SIGINT)

class Status(usage.Options, PIDMixin):
    def postOptions(self):
        dbdir = self.parent.getStoreDirectory()
        serverpid = self.signalServer(0)
        print 'A server is running from the Axiom database %r, PID %d.' % (dbdir, serverpid)


class Options(usage.Options):
    optParameters = [
        ('dbdir', 'd', None, 'Path containing axiom database to configure/create'),
        ]

    optFlags = [
        ('debug', 'b', 'Enable Axiom-level debug logging')]


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
