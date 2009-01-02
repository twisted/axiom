# Copyright (c) 2008 Divmod.  See LICENSE for details.

"""
Tests for the Axiom upgrade system.
"""

import sys, StringIO

from zope.interface import Interface
from zope.interface.verify import verifyObject

from twisted.trial import unittest
from twisted.python import filepath
from twisted.application.service import IService
from twisted.internet.defer import maybeDeferred
from twisted.python.reflect import namedModule
from twisted.python import log

from axiom.iaxiom import IAxiomaticCommand
from axiom import store, upgrade, item, errors, attributes
from axiom.upgrade import _StoreUpgrade
from axiom.item import declareLegacyItem
from axiom.scripts import axiomatic
from axiom.store import Store
from axiom.substore import SubStore
from axiom.plugins.axiom_plugins import Upgrade
from axiom.test.util import CommandStub



def axiomInvalidate(itemClass):
    """
    Remove the registered item class from the Axiom module system's memory,
    including: the item's current schema, legacy schema declarations, and
    upgraders.

    This makes it possible, for example, to reload a module without Axiom
    complaining about it.

    This API is still in a test module because it is _NOT YET SAFE_ for using
    while databases are open; it does not interact with open databases' caches,
    for example.

    @param itemClass: an Item subclass that you no longer wish to use.
    """
    # Note, be very careful not to use comparison on attributes here.  For
    # example, do not use list.remove(), since it is equality based. -exarkun
    for cascades in attributes._cascadingDeletes.itervalues():
        for i in xrange(len(cascades) - 1, -1, -1):
            if cascades[i].type is itemClass:
                del cascades[i]

    store._typeNameToMostRecentClass.pop(itemClass.typeName, None)

    for (tnam, schever) in item._legacyTypes.keys():
        if tnam == itemClass.typeName:
            item._legacyTypes.pop((tnam, schever))

    for k in upgrade._upgradeRegistry.keys():
        if k[0] == itemClass.typeName:
            upgrade._upgradeRegistry.pop(k)

def axiomInvalidateModule(moduleObject):
    """
    Call L{axiomInvalidate} on all Item subclasses defined in a module.
    """
    for v in moduleObject.__dict__.values():
        if isinstance(v, item.MetaItem):
            axiomInvalidate(v)

schemaModules = []

def loadSchemaModule(name):
    schemaModules.append(namedModule(name))
    result = schemaModules[-1]
    choose(None)
    return result

def choose(module=None):
    """
    Choose among the various "adventurer" modules for upgrade tests.

    @param module: the module object which should next be treated as "current".
    """
    for old in schemaModules:
        axiomInvalidateModule(old)

    if module is not None:
        reload(module)

oldapp = loadSchemaModule('axiom.test.oldapp')

brokenapp = loadSchemaModule('axiom.test.brokenapp')

toonewapp = loadSchemaModule('axiom.test.toonewapp')

morenewapp = loadSchemaModule('axiom.test.morenewapp')

onestepapp = loadSchemaModule('axiom.test.onestepapp')

newapp = loadSchemaModule('axiom.test.newapp')

oldpath = loadSchemaModule('axiom.test.oldpath')

newpath = loadSchemaModule('axiom.test.newpath')

path_postcopy = loadSchemaModule('axiom.test.path_postcopy')

deleteswordapp = loadSchemaModule('axiom.test.deleteswordapp')

class SchemaUpgradeTest(unittest.TestCase):
    def setUp(self):
        self.dbdir = filepath.FilePath(self.mktemp())

    def openStore(self, dbg=False):
        self.currentStore = store.Store(self.dbdir, debug=dbg)
        return self.currentStore

    def closeStore(self):
        self.currentStore.close()
        self.currentStore = None

    def startStoreService(self):
        svc = IService(self.currentStore)
        svc.getServiceNamed("Batch Processing Controller").disownServiceParent()
        svc.startService()

def _logMessagesFrom(f):
    L = []
    log.addObserver(L.append)
    d = maybeDeferred(f)
    def x(ign):
        log.removeObserver(L.append)
        return ign
    return d.addBoth(x).addCallback(lambda ign: L)



def callWithStdoutRedirect(f, *a, **kw):
    """
    Redirect stdout and invoke C{f}.

    @returns: C{(returnValue, stdout})
    """
    output = StringIO.StringIO()
    sys.stdout, stdout = output, sys.stdout
    try:
        result = f(*a, **kw)
    finally:
        sys.stdout = stdout
    return result, output



class SwordUpgradeTest(SchemaUpgradeTest):

    def tearDown(self):
        choose(oldapp)

    def testUnUpgradeableStore(self):
        self._testTwoObjectUpgrade()
        choose(toonewapp)
        self.assertRaises(errors.NoUpgradePathAvailable, self.openStore)

    def testUpgradeWithMissingVersion(self):
        playerID, swordID = self._testTwoObjectUpgrade()
        choose(morenewapp)
        s = self.openStore()
        self.startStoreService()
        def afterUpgrade(result):
            player = s.getItemByID(playerID, autoUpgrade=False)
            sword = s.getItemByID(swordID, autoUpgrade=False)
            self._testPlayerAndSwordState(player, sword)
        return s.whenFullyUpgraded().addCallback(afterUpgrade)


    def test_upgradeSkipVersion(self):
        """
        Verify that an upgrader registered to skip a version can execute properly.
        """
        playerID, swordID = self._testTwoObjectUpgrade()
        choose(onestepapp)
        s = self.openStore()
        self.startStoreService()
        def afterUpgrade(result):
            player = s.getItemByID(playerID, autoUpgrade=False)
            sword = s.getItemByID(swordID, autoUpgrade=False)
            self._testPlayerAndSwordState(player, sword)
        return s.whenFullyUpgraded().addCallback(afterUpgrade)



    def test_loggingAtAppropriateTimes(self):
        """
        Verify that log messages show up when we do upgrade work, but then don't
        when we don't.
        """
        def someLogging(logMessages):
            ok = False
            unrelatedMessages = []
            for msgdict in logMessages:
                msgstr = u''.join(msgdict.get('message', ()))
                if u'finished upgrading' in msgstr:
                    ok = True
                else:
                    unrelatedMessages.append(msgstr)
            self.failUnless(ok, "No messages related to upgrading: %r" % (unrelatedMessages,))
            s = self.openStore()
            def afterUpgrade(noLogMessages):
                for nmsgdict in noLogMessages:
                    mm = u''.join(nmsgdict.get('message', ()))
                    if mm:
                        self.failIfIn(u'finished upgrading', mm)
            self.startStoreService()
            return _logMessagesFrom(s.whenFullyUpgraded
                                    ).addCallback(afterUpgrade)

        return _logMessagesFrom(self.testTwoObjectUpgrade_UseService).addCallback(someLogging)


    def test_basicErrorLogging(self):
        """
        Verify that if an exception is raised in an upgrader, the exception
        will be logged.
        """
        playerID, swordID = self._testTwoObjectUpgrade()
        choose(brokenapp)
        s = self.openStore()
        self.startStoreService()

        def checkException(ign):
            # It's redundant that the errback is called and the failure is
            # logged.  See #2638.
            loggedErrors = self.flushLoggedErrors(errors.ItemUpgradeError)
            self.assertEqual(len(loggedErrors), 1)
            upgradeError = loggedErrors[0]

            loggedErrors = self.flushLoggedErrors(brokenapp.UpgradersAreBrokenHere)
            self.assertEqual(len(loggedErrors), 1)
            originalError = loggedErrors[0]

            oldType = item.declareLegacyItem(
                oldapp.Sword.typeName,
                oldapp.Sword.schemaVersion, {})
            e = upgradeError.value
            self.assertEqual(e.storeID, swordID)
            self.assertIdentical(e.oldType, oldType)
            self.assertIdentical(e.newType, brokenapp.Sword)

        d = s.whenFullyUpgraded()
        d = self.assertFailure(d, errors.ItemUpgradeError)
        d.addCallback(checkException)
        return d


    def _testTwoObjectUpgrade(self):
        choose(oldapp)
        s = self.openStore()
        self.assertIdentical(
            store._typeNameToMostRecentClass[oldapp.Player.typeName],
            oldapp.Player)

        sword = oldapp.Sword(
            store=s,
            name=u'flaming vorpal doom',
            hurtfulness=7)

        player = oldapp.Player(
            store=s,
            name=u'Milton',
            sword=sword)

        self.closeStore()

        # Perform an adjustment.

        return player.storeID, sword.storeID


    def testTwoObjectUpgrade_OuterFirst(self):
        playerID, swordID = self._testTwoObjectUpgrade()
        player, sword = self._testLoadPlayerFirst(playerID, swordID)
        self._testPlayerAndSwordState(player, sword)


    def testTwoObjectUpgrade_InnerFirst(self):
        playerID, swordID = self._testTwoObjectUpgrade()
        player, sword = self._testLoadSwordFirst(playerID, swordID)
        self._testPlayerAndSwordState(player, sword)


    def testTwoObjectUpgrade_AutoOrder(self):
        playerID, swordID = self._testTwoObjectUpgrade()
        player, sword = self._testAutoUpgrade(playerID, swordID)
        self._testPlayerAndSwordState(player, sword)


    def testTwoObjectUpgrade_UseService(self):
        playerID, swordID = self._testTwoObjectUpgrade()
        choose(newapp)
        s = self.openStore()
        self.startStoreService()

        # XXX *this* test really needs 10 or so objects to play with in order
        # to be really valid...

        def afterUpgrade(result):
            player = s.getItemByID(playerID, autoUpgrade=False)
            sword = s.getItemByID(swordID, autoUpgrade=False)
            self._testPlayerAndSwordState(player, sword)

        return s.whenFullyUpgraded().addCallback(afterUpgrade)


    def _testAutoUpgrade(self, playerID, swordID):
        choose(newapp)
        s = self.openStore()

        for dummy in s._upgradeManager.upgradeEverything():
            pass

        player = s.getItemByID(playerID, autoUpgrade=False)
        sword = s.getItemByID(swordID, autoUpgrade=False)

        return player, sword

    def _testLoadPlayerFirst(self, playerID, swordID):
        # Everything old is new again
        choose(newapp)

        s = self.openStore()
        player = s.getItemByID(playerID)
        sword = s.getItemByID(swordID)
        return player, sword

    def _testLoadSwordFirst(self, playerID, swordID):
        choose(newapp)

        s = self.openStore()
        sword = s.getItemByID(swordID)
        player = s.getItemByID(playerID)
        return player, sword

    def _testPlayerAndSwordState(self, player, sword):
        assert not player.__legacy__
        assert not sword.__legacy__
        self.assertEquals(player.name, 'Milton')
        self.failIf(hasattr(player, 'sword'))
        self.assertEquals(sword.name, 'flaming vorpal doom')
        self.assertEquals(sword.damagePerHit, 14)
        self.failIf(hasattr(sword, 'hurtfulness'))
        self.assertEquals(sword.owner.storeID, player.storeID)
        self.assertEquals(type(sword.owner), type(player))
        self.assertEquals(sword.owner, player)
        self.assertEquals(sword.activated, 1)
        self.assertEquals(player.activated, 1)


    def test_multipleLegacyVersions(self):
        """
        If multiple legacy schema versions are present, all of them should be
        upgraded.
        """
        playerID, swordID = self._testTwoObjectUpgrade()

        choose(newapp)
        s = self.openStore()
        self.startStoreService()
        def afterFirstUpgrade(result):
            self.closeStore()

            choose(morenewapp)
            s = self.openStore()
            self.startStoreService()
            return s.whenFullyUpgraded().addCallback(afterSecondUpgrade, s)

        def afterSecondUpgrade(result, store):
            player = store.getItemByID(playerID, autoUpgrade=False)
            sword = store.getItemByID(swordID, autoUpgrade=False)
            self._testPlayerAndSwordState(player, sword)

        return s.whenFullyUpgraded().addCallback(afterFirstUpgrade)



class SubStoreCompat(SwordUpgradeTest):
    def setUp(self):
        self.topdbdir = filepath.FilePath(self.mktemp())
        self.subStoreID = None

    def openStore(self):
        self.currentTopStore = store.Store(self.topdbdir)
        if self.subStoreID is not None:
            self.currentSubStore = self.currentTopStore.getItemByID(self.subStoreID).open()
        else:
            ss = SubStore.createNew(self.currentTopStore,
                                    ['sub'])
            self.subStoreID = ss.storeID
            self.currentSubStore = ss.open()
        return self.currentSubStore

    def closeStore(self):
        self.currentSubStore.close()
        self.currentTopStore.close()
        self.currentSubStore = None
        self.currentTopStore = None

    def startStoreService(self):
        svc = IService(self.currentTopStore)
        svc.getServiceNamed("Batch Processing Controller").disownServiceParent()
        svc.startService()



class PathUpgrade(SchemaUpgradeTest):
    """
    Tests for items with path attributes, using
    registerAttributeCopyingUpgrader.
    """
    def _runPathUpgrade(self, module):
        """
        Load the 'oldpath' module, then upgrade items created from it to the
        versions in the specified module.
        """
        axiomInvalidateModule(module)
        reload(oldpath)
        self.openStore()
        nfp = self.currentStore.newFilePath("pathname")
        oldpath.Path(store=self.currentStore,
                     thePath=nfp)
        self.closeStore()
        axiomInvalidateModule(oldpath)
        reload(module)
        self.openStore()
        self.startStoreService()
        return nfp, self.currentStore.whenFullyUpgraded()


    def testUpgradePath(self):
        """
        Verify that you can upgrade a path attribute in the simplest possible
        way.
        """
        nfp, d = self._runPathUpgrade(newpath)
        def checkPathEquivalence(n):
            self.assertEquals(
                self.currentStore.findUnique(newpath.Path).thePath.path,
                nfp.path)
        return d.addCallback(checkPathEquivalence)


    def test_postCopy(self):
        """
        Ensure that a post-copy function, if specified to
        registerAttributeCopyingUpgrader, is run after item upgrade.
        """
        nfp, d = self._runPathUpgrade(path_postcopy)
        path2 = nfp.child("foo")
        def checkPath(_):
            self.assertEquals(
                self.currentStore.findUnique(path_postcopy.Path).thePath.path,
                path2.path)
        return d.addCallback(checkPath)


oldcirc = loadSchemaModule('axiom.test.oldcirc')

newcirc = loadSchemaModule('axiom.test.newcirc')

oldobsolete = loadSchemaModule('axiom.test.oldobsolete')

newobsolete = loadSchemaModule('axiom.test.newobsolete')


class IObsolete(Interface):
    """
    Interface representing an undesirable feature.
    """

class DeletionTest(SchemaUpgradeTest):
    def testCircular(self):
        """
        If you access an item, B, through a reference on another item, A, which
        is deleted in the course of B's upgrade, you should still get a
        reference to B.
        """
        reload(oldcirc)
        self.openStore()
        b = oldcirc.B(a=oldcirc.A(store=self.currentStore),
                      store=self.currentStore)
        b.a.b = b

        self.closeStore()

        axiomInvalidateModule(oldcirc)
        reload(newcirc)

        self.openStore()
        origA = self.currentStore.findUnique(newcirc.A)
        origB = origA.b
        secondA = self.currentStore.findUnique(newcirc.A)
        secondB = secondA.b
        self.assertEquals(origB, secondB)
        self.assertNotEqual(origA, secondA)

    def testPowerupsFor(self):
        """
        Powerups deleted during upgrades should be omitted from the results of
        powerupsFor.
        """
        reload(oldobsolete)
        self.openStore()
        o = oldobsolete.Obsolete(store=self.currentStore)
        self.currentStore.powerUp(o, IObsolete)
        # sanity check
        self.assertEquals(IObsolete(self.currentStore), o)
        self.closeStore()

        axiomInvalidateModule(oldobsolete)
        reload(newobsolete)
        self.openStore()
        self.assertEquals(list(self.currentStore.powerupsFor(IObsolete)), [])
        self.closeStore()
        axiomInvalidateModule(newobsolete)

    def testPowerupsAdapt(self):
        """
        Powerups deleted during upgrades should be omitted from the results of
        powerupsFor.
        """
        reload(oldobsolete)
        self.openStore()
        o = oldobsolete.Obsolete(store=self.currentStore)
        self.currentStore.powerUp(o, IObsolete)
        # sanity check
        self.assertEquals(IObsolete(self.currentStore), o)
        self.closeStore()

        axiomInvalidateModule(oldobsolete)
        reload(newobsolete)
        self.openStore()
        self.assertEquals(IObsolete(self.currentStore, None), None)
        self.closeStore()
        axiomInvalidateModule(newobsolete)



two_upgrades_old = loadSchemaModule(
    'axiom.test.upgrade_fixtures.two_upgrades_old')

two_upgrades_new = loadSchemaModule(
    'axiom.test.upgrade_fixtures.two_upgrades_new')

reentrant_old = loadSchemaModule(
    'axiom.test.upgrade_fixtures.reentrant_old')

reentrant_new = loadSchemaModule(
    'axiom.test.upgrade_fixtures.reentrant_new')

override_init_old = loadSchemaModule(
    'axiom.test.upgrade_fixtures.override_init_old')

override_init_new = loadSchemaModule(
    'axiom.test.upgrade_fixtures.override_init_new')

replace_attribute_old = loadSchemaModule(
    'axiom.test.upgrade_fixtures.replace_attribute_old')

replace_attribute_new = loadSchemaModule(
    'axiom.test.upgrade_fixtures.replace_attribute_new')

replace_delete_old = loadSchemaModule(
    'axiom.test.upgrade_fixtures.replace_delete_old')

replace_delete_new = loadSchemaModule(
    'axiom.test.upgrade_fixtures.replace_delete_new')


class DuringUpgradeTests(unittest.TestCase):
    """
    Tests for upgraders' interactions with each other and with the Store while
    an upgrader is running.
    """
    def tearDown(self):
        choose(None)


    dbdir = None
    currentStore = None

    def storeWithVersion(self, chosenModule):
        """
        Open a store with a particular module chosen, closing the old store if
        it was open already.
        """
        choose(chosenModule)
        if self.currentStore is not None:
            self.currentStore.close()
        if self.dbdir is None:
            self.dbdir = filepath.FilePath(self.mktemp())
        self.currentStore = store.Store(self.dbdir)
        return self.currentStore


    def test_upgradeLegacyReference(self):
        """
        Let a and b be two items which are being upgraded, instances of item
        types A and B respectively.  a has a reference attribute, x, which
        points to b.  In A's 1to2 upgrader, newA.x is set to oldA.x, which is
        (at that time) a DummyItem, i.e. an item with __legacy__ set to True.

        This is a regression test for a bug in this scenario where caching was
        too aggressive, and a.x would still refer to a legacy item after the
        upgrade was finished.  After performing this upgrade, a.x should refer
        to a B v2, i.e. an upgraded version of b.
        """
        old = self.storeWithVersion(two_upgrades_old)
        storeID = two_upgrades_old.Referrer(
            store=old,
            referee=two_upgrades_old.Referee(store=old)).storeID

        new = self.storeWithVersion(two_upgrades_new)
        referrer = new.getItemByID(storeID)
        referee = referrer.referee
        self.assertTrue(
            isinstance(referee, two_upgrades_new.Referee),
            "%r is a %r but should be %r" % (
                referee, type(referee), two_upgrades_new.Referee))


    def test_reentrantUpgraderFailure(self):
        """
        If, while an upgrader is running, it triggers its own upgrade, there
        should be a loud failure; it's already hard enough to deal with upgrade
        ordering and querying for legacy items; upgraders cannot reasonably be
        written to be correct in the face of reentrancy.
        """
        old = self.storeWithVersion(reentrant_old)
        storeID = reentrant_old.Simple(store=old).storeID
        new = self.storeWithVersion(reentrant_new)
        self.assertRaises(errors.UpgraderRecursion, new.getItemByID, storeID)
        # A whitebox flourish to make sure our state tracking is correct:
        self.failIf(new._upgradeManager._currentlyUpgrading,
                    "No upgraders should currently be in progress.")


    def test_overridenInitializerInUpgrader(self):
        """
        A subclass of Item which overrides __init__ should be cached by the end
        of Item.__init__, so that logic written by the subclass has normal
        caching semantics.
        """
        old = self.storeWithVersion(override_init_old)
        storeID = override_init_old.Simple(store=old).storeID
        new = self.storeWithVersion(override_init_new)
        upgraded = new.getItemByID(storeID)
        simpleSelf, simpleGotItem = upgraded.verify
        self.assertIdentical(upgraded, simpleSelf)
        self.assertIdentical(upgraded, simpleGotItem)


    def _reentrantReferenceForeignUpgrader(self, oldModule, newModule):
        old = self.storeWithVersion(oldModule)
        storeID = oldModule.Referrer(
            store=old, referee=oldModule.Referee(
                store=old, value=oldModule.OLD_VALUE)).storeID
        new = self.storeWithVersion(newModule)
        referrer = new.getItemByID(storeID)
        upgraded = referrer.referee
        self.assertEqual(
            upgraded.value,
            newModule.NEW_VALUE,
            "Upgraded reference does not have new value.")


    def test_referenceModifiedByForeignUpgrader(self):
        """
        If the value of a reference on an Item requires an upgrade and the
        upgrade replaces the value of the reference with a different Item, then
        evaluating the reference attribute on the referrer should result in the
        new value of the attribute.
        """
        self._reentrantReferenceForeignUpgrader(
            replace_attribute_old, replace_attribute_new)


    def test_cascadingDeletedReferenceModifiedByForeignUpgrader(self):
        """
        If the value of a whenDeleted=CASCADE reference on an Item requires an
        upgrade and the upgrade replaces the value of the reference with a new
        Item and then deletes the old value of the reference, then evaluating
        the reference attribute on the referrer should result in the new value
        of the attribute.
        """
        self._reentrantReferenceForeignUpgrader(
            replace_delete_old, replace_delete_new)



class AxiomaticUpgradeTest(unittest.TestCase):
    """
    L{Upgrade} implements an I{axiomatic} subcommand for synchronously
    upgrading all items in a store.
    """
    def setUp(self):
        """
        Create a temporary on-disk Store and an instance of L{Upgrade}.
        """
        self.dbdir = self.mktemp()
        self.store = store.Store(self.dbdir)


    def tearDown(self):
        """
        Close the temporary Store.
        """
        self.store.close()


    def test_providesCommandInterface(self):
        """
        L{Upgrade} provides L{IAxiomaticCommand}.
        """
        self.assertTrue(verifyObject(IAxiomaticCommand, Upgrade))


    def test_axiomaticSubcommand(self):
        """
        L{Upgrade} is available as a subcommand of I{axiomatic}.
        """
        subCommands = axiomatic.Options().subCommands
        [options] = [cmd[2] for cmd in subCommands if cmd[0] == 'upgrade']
        self.assertIdentical(options, Upgrade)


    def test_successOutput(self):
        """
        Upon successful completion of the upgrade, L{Upgrade} writes a success
        message to stdout.
        """
        cmd = Upgrade()
        cmd.parent = CommandStub(self.store, 'upgrade')
        result, output = callWithStdoutRedirect(cmd.parseOptions, [])
        self.assertEqual(output.getvalue(), 'Upgrade complete\n')


    def test_axiomaticUpgradeEverything(self):
        """
        L{Upgrade.upgradeStore} upgrades all L{Item}s.
        """
        choose(oldapp)
        swordID = oldapp.Sword(
            store=self.store, name=u'broadsword', hurtfulness=5).storeID
        self.store.close()

        choose(deleteswordapp)

        cmd = Upgrade()
        cmd.parent = CommandStub(store.Store(self.dbdir), 'upgrade')

        result, output = callWithStdoutRedirect(
            cmd.parseOptions, ['--count', '100'])

        self.store = store.Store(self.dbdir)
        self.assertRaises(
            KeyError, self.store.getItemByID, swordID, autoUpgrade=False)


    def test_axiomaticUpgradeExceptionBubbling(self):
        """
        Exceptions encountered by L{Upgrade.upgradeStore} are handled and
        re-raised as L{errors.ItemUpgradeError} with attributes indicating
        which L{Item} was being upgraded when the exception occurred.
        """
        choose(oldapp)
        swordID = oldapp.Sword(
            store=self.store, name=u'longsword', hurtfulness=4).storeID
        self.store.close()

        choose(brokenapp)
        self.store = store.Store(self.dbdir)

        cmd = Upgrade()
        cmd.parent = CommandStub(self.store, 'upgrade')
        cmd.count = 100

        err = self.assertRaises(
            errors.ItemUpgradeError,
            callWithStdoutRedirect, cmd.upgradeStore, self.store)

        self.assertTrue(
            err.originalFailure.check(brokenapp.UpgradersAreBrokenHere))

        oldType = item.declareLegacyItem(
            oldapp.Sword.typeName,
            oldapp.Sword.schemaVersion, {})
        self.assertEqual(err.storeID, swordID)
        self.assertIdentical(err.oldType, oldType)
        self.assertIdentical(err.newType, brokenapp.Sword)


    def test_axiomaticUpgradePerformFails(self):
        """
        If an exception occurs while upgrading items, L{Upgrade.postOptions}
        reports the item and schema version for which it occurred and returns
        without exception.
        """
        choose(oldapp)
        swordID = oldapp.Sword(
            store=self.store, name=u'rapier', hurtfulness=3).storeID
        self.store.close()

        choose(brokenapp)
        self.store = store.Store(self.dbdir)

        cmd = Upgrade()
        cmd.parent = CommandStub(self.store, 'upgrade')

        result, output = callWithStdoutRedirect(
            cmd.parseOptions, ['--count', '100'])
        lines = output.getvalue().splitlines()

        # Ensure that the original error is output.
        self.assertEqual(lines[0], 'Upgrader error:')
        self.assertTrue(len(lines) > 2)

        oldType = oldapp.Sword
        newType = store._typeNameToMostRecentClass[oldType.typeName]
        msg = cmd.errorMessageFormat % (
            oldType.typeName, swordID, oldType.schemaVersion,
            newType.schemaVersion)
        self.assertTrue(lines[-1].startswith(msg))


    def test_upgradeStoreRecursing(self):
        """
        L{Upgrade} upgrades L{Item}s in substores.
        """
        choose(oldapp)

        ss1 = SubStore.createNew(self.store, ['a'])
        ss2 = SubStore.createNew(self.store, ['b'])

        swordIDs = [
            (ss1.storeID, oldapp.Sword(store=ss1.open(), name=u'foo').storeID),
            (ss2.storeID, oldapp.Sword(store=ss2.open(), name=u'bar').storeID)]

        del ss1, ss2
        self.store.close()

        choose(deleteswordapp)
        self.store = store.Store(self.dbdir)

        cmd = Upgrade()
        cmd.parent = CommandStub(self.store, 'upgrade')

        callWithStdoutRedirect(cmd.parseOptions, [])

        for (ssid, swordID) in swordIDs:
            self.assertRaises(
                KeyError,
                self.store.getItemByID(ssid).open().getItemByID, swordID)


class StoreUpgradeTests(unittest.TestCase):
    """
    Tests for L{upgrade._StoreUgprade}.
    """
    def setUp(self):
        self.store = Store()
        self._upgrader = _StoreUpgrade(self.store)

    def test_queueMultipleVersions(self):
        """
        If multiple schema versions are queued for upgrade, upgrades should be
        attempted for all of them (but only attempted once per version).
        """
        legacy1 = declareLegacyItem('test_type', 1, {})
        legacy2 = declareLegacyItem('test_type', 2, {})
        self._upgrader.queueTypeUpgrade(legacy1)
        self._upgrader.queueTypeUpgrade(legacy2)
        self._upgrader.queueTypeUpgrade(legacy2)
        self.assertEqual(len(self._upgrader._oldTypesRemaining), 2)
