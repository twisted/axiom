====================
 Upgrading schemata
====================

Often, you'll want to change the schema of an item. You might want to
remove attributes, add attributes, or some combination of the two.
Axiom comes with strong built-in support for migrating your data
across schema upgrades.

If you're executing these exercises by hand, keep in mind that
whenever we re-open a store, you should close the store before
continuing. You can close the store by ending your interpreter
session.

.. testsetup::

    from axiom import attributes, item, store
    from tempfile import mkdtemp
    from twisted.python.filepath import FilePath
    tempPath = FilePath(mkdtemp())

.. testcleanup::

    tempPath.remove()

Schema versions and upgrader functions
======================================

A schema version is an integer describing the current revision of the
schema. If you don't specify a schema version, your item's default
schema version is ``1``:

.. doctest::

    >>> class Lollipop(item.Item):
    ...     flavor = attributes.text(allowNone=False)
    ...     yummy = attributes.boolean(default=True)
    >>> Lollipop.schemaVersion
    1

An upgrader is a simple function that receives an old version of the
item and is supposed to return a version of the item with a schema
version that's one higher.

.. note::

    Upgrader functions, like most migration logic, should never be
    removed from your code base.

Enabling upgrading behavior
---------------------------

The upgrading behavior is a service present in every Axiom store. To
enable it, you should adapt the store to the ``IService`` interface to
get a service object, which you can then start. If that doesn't make
any sense to you yet, don't worry -- it's pretty easy:

.. doctest::

    >>> from twisted.application.service import IService
    >>> theStore = store.Store()
    >>> IService(theStore).startService()

Of course, generally, you'll only do this on stores that are persisted
-- otherwise it doesn't make much sense to be upgrading in the first
place.

A simple example: adding a field
================================

A very common schema change would be to add a field. Let's say we have
a series of things you can order at a coffee shop, each of which have
a description and a price:

.. literalinclude:: coffeeshop.py
    :language: python

Let's create a few instances of these:

.. doctest::

   >>> s = store.Store()
   >>> from coffeeshop import ShopItem
   >>> from decimal import Decimal
   >>> fiveBucks = Decimal("5.00")
   >>> ShopItem(store=s, description=u"Coffee", price=fiveBucks)
   ShopItem(description=u'Coffee', price=Decimal('5.00'), storeID=1)@...
   >>> ShopItem(store=s, description=u"Iced Coffee", price=fiveBucks)
   ShopItem(description=u'Iced Coffee', price=Decimal('5.00'), storeID=2)@...
   >>> ShopItem(store=s, description=u"Muffin", price=fiveBucks)
   ShopItem(description=u'Muffin', price=Decimal('5.00'), storeID=3)@...

For analytics purposes, we'd like to also store whether or not a thing
is a drink or food.

TODO: newcoffeeshop.py

Writing upgrade logic to change a value
=======================================

Suppose you have a database with temperature measurements. The
American engineer who originally produced the measurements used
degrees Fahrenheit.

.. literalinclude:: measurements.py
   :language: python

.. doctest::
    :hide:

    >>> storePath = None

.. doctest::

    >>> s = store.Store(storePath)
    >>> from measurements import Measurement
    >>> measurement = Measurement(store=s, temperature=-100, pressure=100)
    >>> measurement.schemaVersion
    1

You decide that it would be better to change the unit from degrees
Fahrenheit to Kelvins. Technically, we don't really want to change the
database *schema*: the attribute type, ``point4decimal``, is entirely
appropriate for temperatures in either unit. However, confusing units
is potentially disastrous. [#units]_

By exacting a schema change, Axiom will take care of all the
conversions for you, and you know that any item you use will have been
converted, so there can be no confusion as to what unit a value is
expressed in.

.. literalinclude:: newmeasurements.py
   :language: python

At this point, we end the process and reload the store.

.. doctest::
   :hide:

    >>> # BEGIN HACK 
    >>> measurement.__dict__["schemaVersion"] = 2
    >>> from decimal import Decimal
    >>> measurement.temperature = Decimal('199.81')
    >>> # END HACK

.. doctest::

    >>> IService(s).startService()
    >>> measurement.schemaVersion
    2
    >>> s.query(Measurement).count()
    1
    >>> s.findUnique(Measurement).temperature
    Decimal('199.81')

Attribute copying upgraders
===========================

One common pattern for upgraders is that they'll re-use most of the
values the old item has.

TODO: write example

Deleting upgraders
==================

Another common pattern for upgraders is to delete an item that was
previously being stored.

TODO: write example

.. rubric:: Footnotes

.. [#units] Confusing different units for the same quantity was the
            core problem that caused the loss of the `Mars Climate
            Orbiter`_.

.. _`Mars Climate Orbiter`: https://en.wikipedia.org/wiki/Mars_Climate_Orbiter
