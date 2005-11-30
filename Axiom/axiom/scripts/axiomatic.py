
import os
import sys
import glob
import errno
import signal

from twisted import plugin
from twisted.python import usage, log
from twisted.scripts import twistd
from twisted.application import app, service

from axiom import plugins

from axiom import iaxiom
from axiom.store import Store

class AxiomaticSubCommandMixin:
    store = property(lambda self: self.parent.getStore())

    def decodeCommandLine(self, cmdline):
        """Turn a byte string from the command line into a unicode string.
        """
        codec = getattr(sys.stdin, 'encoding', None) or sys.getdefaultencoding()
        return unicode(cmdline, codec)

class Start(twistd.ServerOptions):

    def postOptions(self):

        # This does not invoke the super implementation.  At the time this
        # method was implemented, all the super method did was *conditionally*
        # set self['no_save'] to True and take the abspath of self['pidfile'].
        # See below for the irrelevance of those operations.

        app.installReactor(self['reactor'])

        dbdir = self.parent.getStoreDirectory()
        rundir = os.path.join(dbdir, 'run')

        self['no_save'] = True
        self['nodaemon'] = self['nodaemon'] or self['debug']

        if not os.path.exists(rundir):
            os.mkdir(rundir)

        if self['logfile'] is None and not self['nodaemon']:
            logdir = os.path.join(rundir, 'logs')
            if not os.path.exists(logdir):
                os.mkdir(logdir)
            self['logfile'] = os.path.join(logdir, 'axiomatic.log')

        if self['pidfile'] == 'twistd.pid':
            self['pidfile'] = os.path.join(rundir, 'axiomatic.pid')
        elif self['pidfile']:
            self['pidfile'] = os.path.abspath(self['pidfile'])

        twistd.checkPID(self['pidfile'])

        S = self.parent.getStore()

        oldstdout = sys.stdout
        oldstderr = sys.stderr

        twistd.startLogging(
            self['logfile'],
            self['syslog'],
            self['prefix'],
            self['nodaemon'])
        app.initialLog()

        application = service.Application("Axiom Service")
        service.IService(S).setServiceParent(application)

        twistd.startApplication(self, application)
        app.runReactorWithLogging(self, oldstdout, oldstderr)
        twistd.removePID(self['pidfile'])
        app.reportProfile(
            self['report-profile'],
            service.IProcess(application).processName)
        log.msg("Server Shut Down.")


class PIDMixin:

    def _sendSignal(self, signal):
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

    def subCommands():
        def get(self):
            for plg in plugin.getPlugins(iaxiom.IAxiomaticCommand, plugins):
                try:
                    yield (plg.name, None, plg, plg.description)
                except AttributeError:
                    raise RuntimeError("Maldefined plugin: %r" % (plg,))
            yield ('start', None, Start, 'Launch the given Axiom database')
            yield ('stop', None, Stop, 'Stop the server running from the given Axiom database')
            yield ('status', None, Status, 'Report whether a server is running from the given Axiom database')
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
        if self.store is None:
            self.store = Store(self.getStoreDirectory())
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
