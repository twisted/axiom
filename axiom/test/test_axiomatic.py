# Copyright 2006-2009 Divmod, Inc.  See LICENSE file for details

"""
Tests for L{axiom.scripts.axiomatic}.
"""

import sys, os, signal, io, six

from zope.interface import implementer

from twisted.python.log import msg
from twisted.python.filepath import FilePath
from twisted.python.procutils import which
from twisted.python.runtime import platform
from twisted.trial.unittest import SkipTest, TestCase
from twisted.plugin import IPlugin
from twisted.internet import reactor
from twisted.internet.task import deferLater
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.defer import Deferred
from twisted.internet.error import ProcessTerminated
from twisted.application.service import IService, IServiceCollection

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import boolean
from axiom.scripts import axiomatic
from axiom.listversions import SystemVersion
from axiom.iaxiom import IAxiomaticCommand
from axiom.test.util import callWithStdoutRedirect
from twisted.plugins.axiom_plugins import AxiomaticStart

from axiom.test.reactorimporthelper import SomeItem


@implementer(IService)
class RecorderService(Item):
    """
    Minimal L{IService} implementation which remembers if it was ever started.
    This is used by tests to make sure services get started when they should
    be.
    """
    started = boolean(
        doc="""
        A flag which is initially false and set to true once C{startService} is
        called.
        """, default=False)

    name = "recorder"

    def setServiceParent(self, parent):
        """
        Do the standard Axiom thing to make sure this service becomes a child
        of the top-level store service.
        """
        IServiceCollection(parent).addService(self)


    def startService(self):
        """
        Remember that this method was called.
        """
        self.started = True


    def stopService(self):
        """
        Ignore this event.
        """



class StartTests(TestCase):
    """
    Test the axiomatic start sub-command.
    """
    maxDiff = None
    def setUp(self):
        """
        Work around Twisted #3178 by tricking trial into thinking something
        asynchronous is happening.
        """
        return deferLater(reactor, 0, lambda: None)


    def _getRunDir(self, dbdir):
        return dbdir.child("run")


    def _getLogDir(self, dbdir):
        return self._getRunDir(dbdir).child("logs")


    def test_getArguments(self):
        """
        L{Start.getArguments} adds a I{--pidfile} argument if one is not
        present and a I{--logfile} argument if one is not present and
        daemonization is enabled and adds a I{--dbdir} argument pointing at the
        store it is passed. It also adds I{--journal-mode} if this is passed.
        """
        dbdir = FilePath(self.mktemp())
        store = Store(dbdir, journalMode='WAL')
        run = self._getRunDir(dbdir)
        logs = self._getLogDir(dbdir)
        start = axiomatic.Start()

        logfileArg = ["--logfile", logs.child("axiomatic.log").path]

        # twistd on Windows doesn't support PID files, so on Windows,
        # getArguments should *not* add --pidfile.
        if platform.isWindows():
            pidfileArg = []
        else:
            pidfileArg = ["--pidfile", run.child("axiomatic.pid").path]
        restArg = [
            "axiomatic-start", "--dbdir", dbdir.path, "--journal-mode", b"WAL"]

        self.assertEqual(
            start.getArguments(store, []),
            logfileArg + pidfileArg + restArg)
        self.assertEqual(
            start.getArguments(store, ["--logfile=foo"]),
            ["--logfile=foo"] + pidfileArg + restArg)
        self.assertEqual(
            start.getArguments(store, ["--logfile", "foo"]),
            ["--logfile", "foo"] + pidfileArg + restArg)
        self.assertEqual(
            start.getArguments(store, ["-l", "foo"]),
            ["-l", "foo"] + pidfileArg + restArg)
        self.assertEqual(
            start.getArguments(store, ["--nodaemon"]),
            ["--nodaemon"] + pidfileArg + restArg)
        self.assertEqual(
            start.getArguments(store, ["-n"]),
            ["-n"] + pidfileArg + restArg)
        self.assertEqual(
            start.getArguments(store, ["--pidfile=foo"]),
            ["--pidfile=foo"] + logfileArg + restArg)
        self.assertEqual(
            start.getArguments(store, ["--pidfile", "foo"]),
            ["--pidfile", "foo"] + logfileArg + restArg)


    def test_logDirectoryCreated(self):
        """
        If L{Start.getArguments} adds a I{--logfile} argument, it creates the
        necessary directory.
        """
        dbdir = FilePath(self.mktemp())
        store = Store(dbdir)
        start = axiomatic.Start()
        start.getArguments(store, ["-l", "foo"])
        self.assertFalse(self._getLogDir(dbdir).exists())
        start.getArguments(store, [])
        self.assertTrue(self._getLogDir(dbdir).exists())


    def test_parseOptions(self):
        """
        L{Start.parseOptions} adds axiomatic-suitable defaults for any
        unspecified parameters and then calls L{twistd.run} with the modified
        argument list.
        """
        argv = []
        def fakeRun():
            argv.extend(sys.argv)
        options = axiomatic.Options()
        options['dbdir'] = dbdir = self.mktemp()
        start = axiomatic.Start()
        start.parent = options
        start.run = fakeRun
        original = sys.argv[:]
        try:
            start.parseOptions(["-l", "foo", "--pidfile", "bar"])
        finally:
            sys.argv[:] = original
        self.assertEqual(
            argv,
            [sys.argv[0],
             "-l", "foo", "--pidfile", "bar",
             "axiomatic-start", "--dbdir", os.path.abspath(dbdir)])


    def test_parseOptionsHelp(self):
        """
        L{Start.parseOptions} writes usage information to stdout if C{"--help"}
        is in the argument list it is passed and L{twistd.run} is not called.
        """
        start = axiomatic.Start()
        start.run = None
        result, output = callWithStdoutRedirect(self.assertRaises, SystemExit, start.parseOptions, ["--help"])

        # Some random options that should be present.  This is a bad test
        # because we don't control what C{opt_help} actually does and we don't
        # even really care as long as it's the same as what I{twistd --help}
        # does.  We could try running them both and comparing, but then we'd
        # still want to do some sanity check against one of them in case we end
        # up getting the twistd version incorrectly somehow... -exarkun
        self.assertIn("--reactor", output.getvalue())
        if not platform.isWindows():
            # This isn't an option on Windows, so it shouldn't be there.
            self.assertIn("--uid", output.getvalue())

        # Also, we don't want to see twistd plugins here.
        self.assertNotIn("axiomatic-start", output.getvalue())



    def test_checkSystemVersion(self):
        """
        The L{IService} returned by L{AxiomaticStart.makeService} calls
        L{checkSystemVersion} with its store when it is started.

        This is done for I{axiomatic start} rather than somewhere in the
        implementation of L{Store} so that it happens only once per server
        startup.  The overhead of doing it whenever a store is opened is
        non-trivial.
        """
        dbdir = self.mktemp()
        store = Store(dbdir)
        service = AxiomaticStart.makeService(
            {'dbdir': dbdir, 'debug': False, 'journal-mode': None})
        self.assertEqual(store.query(SystemVersion).count(), 0)
        service.startService()
        self.assertEqual(store.query(SystemVersion).count(), 1)
        return service.stopService()


    def test_axiomOptions(self):
        """
        L{AxiomaticStart.options} takes database location, debug, and
        journal mode setting parameters.
        """
        options = AxiomaticStart.options()
        options.parseOptions([])
        self.assertEqual(options['dbdir'], None)
        self.assertFalse(options['debug'])
        self.assertEqual(options['journal-mode'], None)
        options.parseOptions(
            ["--dbdir", "foo", "--debug", "--journal-mode", "WAL"])
        self.assertEqual(options['dbdir'], 'foo')
        self.assertTrue(options['debug'])
        self.assertEqual(options['journal-mode'], 'WAL')


    def test_makeService(self):
        """
        L{AxiomaticStart.makeService} returns the L{IService} powerup of the
        L{Store} at the directory in the options object it is passed.
        """
        dbdir = FilePath(self.mktemp())
        store = Store(dbdir)
        recorder = RecorderService(store=store)
        self.assertFalse(recorder.started)
        store.powerUp(recorder, IService)
        store.close()

        service = AxiomaticStart.makeService(
            {'dbdir': dbdir, 'debug': False, 'journal-mode': None})
        service.startService()
        service.stopService()

        store = Store(dbdir)
        self.assertTrue(store.getItemByID(recorder.storeID).started)


    def _getAxiomaticScript(self):
        here = FilePath(__file__)
        # Try to find it relative to the source of this test.
        bin = here.parent().parent().parent().child("bin")
        axiomatic = bin.child("axiomatic")
        if axiomatic.exists():
            # Great, use that one.
            axiomatic = axiomatic.path
        else:
            # Try to find it on the path, instead.
            axiomatics = which("axiomatic")
            if axiomatics:
                # Great, it was on the path.
                axiomatic = axiomatics[0]
            else:
                # Nope, not there, give up.
                raise SkipTest(
                    "Could not find axiomatic script on path or at {}".format(
                        axiomatic.path))
        return axiomatic


    def test_reactorSelection(self):
        """
        L{AxiomaticStart} optionally takes the name of a reactor in the form
        --reactor [shortName] and installs it instead of the default reactor.
        """
        # Since this process is already hopelessly distant from the state in
        # which I{axiomatic start} operates, it would make no sense to try a
        # functional test of this behavior in this process.  Since the
        # behavior being tested involves lots of subtle interactions between
        # lots of different pieces of code (the reactor might get installed
        # at the end of a ten-deep chain of imports going through as many
        # different projects), it also makes no sense to try to make this a
        # unit test.  So, start a child process and try to use the alternate
        # reactor functionality there.

        axiomatic = self._getAxiomaticScript()

        # Create a store for the child process to use and put an item in it.
        # This will force an import of the module that defines that item's
        # class when the child process starts.  The module imports the default
        # reactor at the top-level, making this the worst-case for the reactor
        # selection code.
        storePath = self.mktemp()
        store = Store(storePath)
        SomeItem(store=store)
        store.close()

        # Install select reactor because it is available on all platforms, and
        # it is still an error to try to install the select reactor even if
        # the already installed reactor was the select reactor.
        argv = [
            sys.executable,
            axiomatic, "-d", storePath,
            "start", "--reactor", "select", "-n"]
        expected = [
            "reactor class: twisted.internet.selectreactor.SelectReactor.",
            "reactor class: <class 'twisted.internet.selectreactor.SelectReactor'>"]
        proto, complete = AxiomaticStartProcessProtocol.protocolAndDeferred(expected)

        environ = os.environ.copy()
        reactor.spawnProcess(proto, sys.executable, argv, env=environ)
        return complete


    def test_reactorSelectionLongOptionStyle(self):
        """
        L{AxiomaticStart} optionally takes the name of a reactor in the form
        --reactor=[shortName] and installs it instead of the default reactor.
        """

        axiomatic = self._getAxiomaticScript()

        # Create a store for the child process to use and put an item in it.
        # This will force an import of the module that defines that item's
        # class when the child process starts.  The module imports the default
        # reactor at the top-level, making this the worst-case for the reactor
        # selection code.
        storePath = self.mktemp()
        store = Store(storePath)
        SomeItem(store=store)
        store.close()

        # Install select reactor because it is available on all platforms, and
        # it is still an error to try to install the select reactor even if
        # the already installed reactor was the select reactor.
        argv = [
            sys.executable,
            axiomatic, "-d", storePath,
            "start", "--reactor=select", "-n"]
        expected = [
            "reactor class: twisted.internet.selectreactor.SelectReactor.",
            "reactor class: <class 'twisted.internet.selectreactor.SelectReactor'>"]
        proto, complete = AxiomaticStartProcessProtocol.protocolAndDeferred(expected)

        environ = os.environ.copy()
        reactor.spawnProcess(proto, sys.executable, argv, env=environ)
        return complete


    def test_reactorSelectionShortOptionStyle(self):
        """
        L{AxiomaticStart} optionally takes the name of a reactor in the form
        -r [shortName] and installs it instead of the default reactor.
        """

        axiomatic = self._getAxiomaticScript()

        # Create a store for the child process to use and put an item in it.
        # This will force an import of the module that defines that item's
        # class when the child process starts.  The module imports the default
        # reactor at the top-level, making this the worst-case for the reactor
        # selection code.
        storePath = self.mktemp()
        store = Store(storePath)
        SomeItem(store=store)
        store.close()

        # Install select reactor because it is available on all platforms, and
        # it is still an error to try to install the select reactor even if
        # the already installed reactor was the select reactor.
        argv = [
            sys.executable,
            axiomatic, "-d", storePath,
            "start", "-r", "select", "-n"]
        expected = [
            "reactor class: twisted.internet.selectreactor.SelectReactor.",
            "reactor class: <class 'twisted.internet.selectreactor.SelectReactor'>"]
        proto, complete = AxiomaticStartProcessProtocol.protocolAndDeferred(expected)

        environ = os.environ.copy()
        reactor.spawnProcess(proto, sys.executable, argv, env=environ)
        return complete



class AxiomaticStartProcessProtocol(ProcessProtocol):
    """
    L{AxiomaticStartProcessProtocol} watches an I{axiomatic start} process
    and fires a L{Deferred} when it sees either successful reactor
    installation or process termination.

    @ivar _success: A flag which is C{False} until the expected text is found
        in the child's stdout and C{True} thereafter.

    @ivar _output: A C{str} giving all of the stdout from the child received
        thus far.
    """
    _success = False
    _output = ""


    def protocolAndDeferred(cls, expected):
        """
        Create and return an L{AxiomaticStartProcessProtocol} and a
        L{Deferred}.  The L{Deferred} will fire when the protocol receives
        the given string on standard out or when the process ends, whichever
        comes first.
        """
        proto = cls()
        proto._complete = Deferred()
        proto._expected = expected
        return proto, proto._complete
    protocolAndDeferred = classmethod(protocolAndDeferred)


    def errReceived(self, bytes):
        """
        Report the given unexpected stderr data.
        """
        msg("Received stderr from axiomatic: {!r}".format(bytes))


    def outReceived(self, bytes):
        """
        Add the given bytes to the output buffer and check to see if the
        reactor has been installed successfully, firing the completion
        L{Deferred} if so.
        """
        msg("Received stdout from axiomatic: {!r}".format(bytes))
        self._output += six.ensure_str(bytes)
        if not self._success:
            for line in self._output.splitlines():
                for expectedLine in self._expected:
                    if expectedLine in line:
                        msg("Received expected output")
                        self._success = True
                        self.transport.signalProcess("TERM")


    def processEnded(self, reason):
        """
        Check that the process exited in the way expected and that the required
        text has been found in its output and fire the result L{Deferred} with
        either a value or a failure.
        """
        self._complete, result = None, self._complete
        if self._success:
            if platform.isWindows() or (
                # Windows can't tell that we SIGTERM'd it, so sorry.
                reason.check(ProcessTerminated) and
                reason.value.signal == signal.SIGTERM):
                result.callback(None)
                return
        # Something went wrong.
        result.errback(reason)



class TestMisc(TestCase):
    """
    Test things not directly involving running axiomatic commands.
    """
    def test_axiomaticCommandProvides(self):
        """
        Test that AxiomaticCommand itself does not provide IAxiomaticCommand or
        IPlugin, but subclasses do.
        """
        self.assertFalse(IAxiomaticCommand.providedBy(axiomatic.AxiomaticCommand), 'IAxiomaticCommand provided')
        self.assertFalse(IPlugin.providedBy(axiomatic.AxiomaticCommand), 'IPlugin provided')

        class _TestSubClass(axiomatic.AxiomaticCommand):
            pass

        self.assertTrue(IAxiomaticCommand.providedBy(_TestSubClass), 'IAxiomaticCommand not provided')
        self.assertTrue(IPlugin.providedBy(_TestSubClass), 'IPlugin not provided')



class AxiomaticTests(TestCase):
    """
    Test things relating to the I{axiomatic} command itself.
    """
    def test_journalMode(self):
        """
        I{axiomatic} sets the journal mode of the store according to
        I{--journal-mode}.
        """
        options = axiomatic.Options()
        options['dbdir'] = self.mktemp()
        options['journal-mode'] = 'WAL'
        self.assertEqual(options.getStore().journalMode, u'WAL')
