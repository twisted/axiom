# Copyright 2006 Divmod, Inc.  See LICENSE file for details

"""
Tests for L{axiom.scripts.axiomatic}.
"""

import sys, os, StringIO

from zope.interface import implements

from twisted.python.filepath import FilePath
from twisted.application.service import IService, IServiceCollection
from twisted.trial.unittest import TestCase
from twisted.plugin import IPlugin

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import boolean
from axiom.scripts import axiomatic
from axiom.iaxiom import IAxiomaticCommand
from twisted.plugins.axiom_plugins import AxiomaticStart


class RecorderService(Item):
    """
    Minimal L{IService} implementation which remembers if it was ever started.
    This is used by tests to make sure services get started when they should
    be.
    """
    implements(IService)

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
    def _getRunDir(self, dbdir):
        return dbdir.child("run")


    def _getLogDir(self, dbdir):
        return self._getRunDir(dbdir).child("logs")


    def test_getArguments(self):
        """
        L{Start.getArguments} adds a I{--pidfile} argument if one is not
        present and a I{--logfile} argument if one is not present and
        daemonization is enabled and adds a I{--dbdir} argument pointing at the
        store it is passed.
        """
        dbdir = FilePath(self.mktemp())
        store = Store(dbdir)
        run = self._getRunDir(dbdir)
        logs = self._getLogDir(dbdir)
        start = axiomatic.Start()

        logfileArg = ["--logfile", logs.child("axiomatic.log").path]
        pidfileArg = ["--pidfile", run.child("axiomatic.pid").path]
        restArg = ["axiomatic-start", "--dbdir", dbdir.path]

        self.assertEqual(
            start.getArguments(store, []),
            logfileArg + pidfileArg + restArg)
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
            start.getArguments(store, ["--pidfile", "foo"]),
            ["--pidfile", "foo"] + logfileArg + restArg)


    def test_logDirectoryCreated(self):
        """
        If L{Start.getArguments} adds a I{--logfile} argument, it creates the
        necessary directory.\
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
        original = sys.stdout
        sys.stdout = stdout = StringIO.StringIO()
        try:
            self.assertRaises(SystemExit, start.parseOptions, ["--help"])
        finally:
            sys.stdout = original

        # Some random options that should be present.  This is a bad test
        # because we don't control what C{opt_help} actually does and we don't
        # even really care as long as it's the same as what I{twistd --help}
        # does.  We could try running them both and comparing, but then we'd
        # still want to do some sanity check against one of them in case we end
        # up getting the twistd version incorrectly somehow... -exarkun
        self.assertIn("--reactor", stdout.getvalue())
        self.assertIn("--uid", stdout.getvalue())

        # Also, we don't want to see twistd plugins here.
        self.assertNotIn("axiomatic-start", stdout.getvalue())


    def test_axiomOptions(self):
        """
        L{AxiomaticStart.options} takes database location and debug setting
        parameters.
        """
        options = AxiomaticStart.options()
        options.parseOptions([])
        self.assertEqual(options['dbdir'], None)
        self.assertFalse(options['debug'])
        options.parseOptions(["--dbdir", "foo", "--debug"])
        self.assertEqual(options['dbdir'], 'foo')
        self.assertTrue(options['debug'])


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

        service = AxiomaticStart.makeService({"dbdir": dbdir, "debug": False})
        service.startService()
        service.stopService()

        store = Store(dbdir)
        self.assertTrue(store.getItemByID(recorder.storeID).started)



class TestMisc(TestCase):
    """
    Test things not directly involving running axiomatic commands.
    """
    def test_axiomaticCommandProvides(self):
        """
        Test that AxiomaticCommand itself does not provide IAxiomaticCommand or
        IPlugin, but subclasses do.
        """
        self.failIf(IAxiomaticCommand.providedBy(axiomatic.AxiomaticCommand), 'IAxiomaticCommand provided')
        self.failIf(IPlugin.providedBy(axiomatic.AxiomaticCommand), 'IPlugin provided')

        class _TestSubClass(axiomatic.AxiomaticCommand):
            pass

        self.failUnless(IAxiomaticCommand.providedBy(_TestSubClass), 'IAxiomaticCommand not provided')
        self.failUnless(IPlugin.providedBy(_TestSubClass), 'IPlugin not provided')
