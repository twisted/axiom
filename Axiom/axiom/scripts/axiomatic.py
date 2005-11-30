
import sys
import glob

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
    def runApp(self):
        twistd.checkPID(self['pidfile'])
        app.installReactor(self['reactor'])
        S = self.parent.getStore()
        self['nodaemon'] = self['nodaemon'] or self['debug']
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

    def postOptions(self):
        self['no_save'] = True
        twistd.ServerOptions.postOptions(self)
        self.runApp()

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
            yield ('start', None, Start, 'Launch the given Axiomatic database')
        return get,
    subCommands = property(*subCommands())

    store = None

    def usedb(self, potentialdb):
        yn = raw_input("Use database %r? (Y/n) " % (potentialdb,))
        if yn.lower() in ('y', 'yes', ''):
            self['dbdir'] = potentialdb
        else:
            raise usage.UsageError('Select another database with the -d option, then.')

    def getStore(self):
        if self.store is None:
            if self['dbdir'] is None:
                possibilities = glob.glob('*.axiom')
                if len(possibilities) > 1:
                    raise usage.UsageError("Multiple databases found here, please select one with the -d option: %s" %
                                           (' '.join(possibilities),))
                elif len(possibilities) == 1:
                    self.usedb(possibilities[0])
                else:
                    self.usedb(self.subCommand + '.axiom')
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
