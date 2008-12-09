# Copyright 2008 Divmod, Inc.
# See LICENSE file for details

"""
Tests for Axiom store version history.
"""

import sys, StringIO
from twisted.trial import unittest
from twisted.python.versions import Version

from axiom.store import Store
from axiom import version as axiom_version
from axiom.listversions import (getSystemVersions,
                                SystemVersion,
                                checkSystemVersion)

from axiom.scripts.axiomatic import Options as AxiomaticOptions
from axiom.test.util import CommandStubMixin
from axiom.plugins.axiom_plugins import ListVersions

class SystemVersionTests(unittest.TestCase, CommandStubMixin):
    """
    Tests for recording the versions of software used to open a store
    throughout its lifetime.
    """

    def setUp(self):
        """
        Create an on-disk store.
        """
        self.dbdir = self.mktemp()
        self.store = Store(self.dbdir)


    def _reopenStore(self):
        """
        Close the store and reopen it.
        """
        self.store.close()
        self.store = Store(self.dbdir)


    def test_getSystemVersions(self):
        """
        L{getSystemVersions} returns all the version plugins it finds.
        """
        someVersions = [Version("foo", 1, 2, 3),
                        Version("baz", 0, 0, 1)]
        def getSomeVersions(iface, package):
            return someVersions
        self.assertEqual(getSystemVersions(getSomeVersions),
                         someVersions)

    def test_checkSystemVersion(self):
        """
         Calling checkSystemVersion:
            1. Doesn't duplicate the system version when called with the
               same software package versions.
            2. Creates a new system version when one of the software
               package versions has changed.
            3. Notices and creates a new system version when the system
               config has reverted to a previous state.
        """
        versions = [Version("foo", 1, 2, 3)]

        checkSystemVersion(self.store, versions)
        checkSystemVersion(self.store, versions)

        query_results = list(self.store.query(SystemVersion))
        self.assertEquals(len(query_results), 1)

        # Adjust a version number and try again.
        v = versions[0]
        versions[0] = Version(v.package, v.major, v.minor + 1, v.micro)
        checkSystemVersion(self.store, versions)

        query_results = list(self.store.query(SystemVersion))
        self.assertEquals(len(query_results), 2)

        # Revert the version number and try again.
        versions[0] = v

        checkSystemVersion(self.store, versions)
        query_results = list(self.store.query(SystemVersion))
        self.assertEquals(len(query_results), 3)

        # Reopening the store does not duplicate the version.
        self._reopenStore()
        query_results = list(self.store.query(SystemVersion))
        self.assertEquals(len(query_results), 3)


    def test_commandLine(self):
        """
        L{ListVersions} will list versions of code used in this store when
        invoked as an axiomatic subcommand.
        """
        checkSystemVersion(self.store)

        out = StringIO.StringIO()
        self.patch(sys, 'stdout', out)
        lv = ListVersions()
        lv.parent = self
        lv.parseOptions([])
        result = out.getvalue()
        self.assertSubstring("axiom: " + axiom_version.short(), result)


    def test_axiomaticSubcommand(self):
        """
        L{ListVersions} is available as a subcommand of I{axiomatic}.
        """
        subCommands = AxiomaticOptions().subCommands
        [options] = [cmd[2] for cmd in subCommands if cmd[0] == 'list-version']
        self.assertIdentical(options, ListVersions)
