========
 Stores
========

So far, we've created items, but never actually put them in a
database. Axiom "databases" are called stores.

To create a store, just call ``axiom.store.Store()``. By default, that
will create an in-memory store. Obviously, in-memory stores aren't
persisted.

.. testsetup::

    from axiom.store import Store

.. doctest::

    >>> inMemoryStore = Store()

To create a persisted store, pass either a path as a string, or a
``twisted.python.filepath.FilePath`` to the store constructor:

.. doctest::

    >>> persistedStore = Store("mystore")

Adding objects to stores
========================

You can either set an item's store when you create it, or by setting
its store attribute later:

.. testsetup::

    from person import Person

.. doctest::

     >>> store = Store()
     >>> alice = Person(store=store, name=u"Alice")
     >>> bob = Person(name=u"Bob")
     >>> bob.store = store
     >>> assert alice.store is bob.store is store

Basic querying
==============

Once we have some objects in a store, we can query them. Simple
queries take the item class you want to get instances of, and the
usual querying suspects:

- comparisons (filters)
- limits and offsets
- sorting

The result returned by a query is a generator, so we'll call ``list``
on it to show its contents.

.. doctest::

    >>> people = list(store.query(Person, sort=Person.name.ascending))
    >>> assert people == [alice, bob]
    >>> person, = store.query(Person, sort=Person.name.ascending, limit=1)
    >>> assert person is alice
    >>> person, = store.query(Person, sort=Person.name.ascending, limit=1, offset=1)
    >>> assert person is bob

Finding unique objects
======================

Since finding exactly one object is such a common pattern, there's an
easier shorthand for it called ``findUnique``.

.. doctest::

    >>> person = store.findUnique(Person, Person.name == u"Alice")
    >>> assert person is alice

Since you're expecting to find a single object, ``findUnique`` will
raise an exception if there is more than one:

.. doctest::

    >>> secondAlice = Person(store=store, name=u"Alice")
    >>> store.findUnique(Person, Person.name == u"Alice")
    Traceback (most recent call last):
    ...
    DuplicateUniqueItem: (person.Person.name = u'Alice', [...])

Similarly, it will raise an exception if there are none:

.. doctest::

    >>> store.findUnique(Person, Person.name == u"Nobody")
    Traceback (most recent call last):
    ...
    ItemNotFound: person.Person.name = u'Nobody'


Creating items unless they exist already
========================================

Sometimes, you want to create an object if it does not exist, or
update an object if it does. Axiom calls this ``findOrCreate``.

.. doctest::

    >>> newAlice = store.findOrCreate(Person, name=u"Alice")
    >>> assert newAlice is alice, "returns the existing object"
    >>> charlie = store.findOrCreate(Person, name=u"Charlie")


Getting parts of the data
=========================

Often, you only want part of the data instead of the entire stored
item using ``getColumn``. (This will once again produce a lazy
iterator, so we will use ``list`` to consume it.)

.. testsetup::

    from bunny import Bunny

.. doctest::

    >>> bugs = Bunny(store=store, timesPetted=1)
    >>> fluffy = Bunny(store=store, timesPetted=2)
    >>> thumper = Bunny(store=store, timesPetted=3)
    >>> query = store.query(Bunny, sort=Bunny.timesPetted.ascending)
    >>> assert list(query.getColumn("timesPetted")) == [1, 2, 3]


Aggregate data: sums, counts, averages
======================================

You can sum over all the attributes in a store:

.. doctest::

    >>> assert store.sum(Bunny.timesPetted) == 6

Usually, it's more useful to do it over a query than over all items:

.. doctest::

    >>> query = store.query(Bunny, Bunny.timesPetted > 1).getColumn("timesPetted")
    >>> assert query.sum() == 5

While you could also do this by using Python's builtin ``sum``
function to get the same result. The principal difference is that with
the query method, the summing is actually done inside the database.

You can also count how many items there are in a query.

.. doctest::

    >>> assert query.count() == 2

You can also average values:

.. doctest::

    >>> assert query.average() == 2.5

Notice how we're re-using the query object. Queries are lazy: they're
only executed when you actually need an item. For example, if an item
is created or modified so that it suddenly is affected by the query,
you get the appropriate result:

.. doctest::

    >>> bugs.timesPetted += 1
    >>> assert query.count() == 3
