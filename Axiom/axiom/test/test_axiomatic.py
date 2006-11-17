# Copyright 2006 Divmod, Inc.  See LICENSE file for details

from twisted.application import app
from twisted.python.reflect import prefixedMethods
from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.scripts import axiomatic


class MockStart(axiomatic.Start):
    """
    We want to test L{axiomatic.Start} but we don't want to actually start
    any applications.
    """
    def _startApplication(self):
        pass

    def _removePID(self):
        pass


class TestStart(TestCase):
    """
    Test the axiomatic start sub-command.
    """

    # app methods
    def app_initialLog(self):
        pass

    def app_installReactor(self, name):
        self.log.append(('installReactor', name))

    def app_reportProfile(self, profile, processName):
        pass

    def app_runReactorWithLogging(self, options, stdout, stderr):
        pass


    def _replaceAppMethods(self):
        """
        Mask over methods in the L{app} module with methods from this class
        that start with 'app_'.
        """
        prefix = 'app_'
        replacedMethods = {}
        for method in prefixedMethods(self, 'app_'):
            name = method.__name__[len(prefix):]
            replacedMethods[name] = getattr(app, name)
            setattr(app, name, method)
        return replacedMethods


    def _restoreAppMethods(self, methods):
        """
        Replace any methods in L{app} with methods from parameter C{methods}.
        """
        for name, method in methods.iteritems():
            setattr(app, name, method)


    def _makeStart(self):
        """
        Do everything necessary to make a new, working L{MockStart} object.
        """
        dbdir = self.mktemp()
        # create a store so axiomatic.Options() can work properly
        s = Store(dbdir)
        s.close()
        parent = axiomatic.Options()
        parent.parseOptions(['-d', dbdir])
        start = MockStart()
        start.parent = parent
        return start


    def setUp(self):
        self.log = []
        self._oldMethods = self._replaceAppMethods()
        self.start = self._makeStart()


    def tearDown(self):
        self._restoreAppMethods(self._oldMethods)


    def test_noReactorSpecified(self):
        """
        Check that no reactor is installed if no reactor is specified.
        """
        self.start.parseOptions([])
        self.assertEqual(self.log, [])


    def test_reactorSpecified(self):
        """
        Check that a reactor is installed if it is specified.
        """
        self.start.parseOptions(['--reactor', 'select'])
        self.assertEqual(self.log, [('installReactor', 'select')])
