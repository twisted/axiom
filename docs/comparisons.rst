=====================================
 More advanced attribute comparisons
=====================================

Axiom provides a few tools for more advanced querying patterns.

.. testsetup::

    from axiom.store import Store
    from person import Person

Checking if something is part of a fixed set
============================================

A common pattern is trying to find all items where some attribute is a
member (or not a member) of some fixed set. Axiom provides ``oneOf``
and ``notOneOf`` for this.

To demonstrate this, let's create a store with some people in it:

.. doctest::

   >>> store = Store()
   >>> audrey = Person(store=store, name=u"audreyr")
   >>> pydanny = Person(store=store, name=u"pydanny")
   >>> lvh = Person(store=store, name=u"lvh")


There's a secret club for people who like coffee ice cream:

.. doctest::

   >>> secretClubMemberNames = [u"pydanny", u"lvh"]

We can create a comparison, which we'll call ``inSecretClub``, that
checks if a person's name is in the list of secret club member names.
Of course, you could just plug this into the query expression directly.

.. doctest::

   >>> inSecretClub = Person.name.oneOf(secretClubMemberNames)
   >>> list(store.query(Person, inSecretClub, sort=Person.name.ascending))
   [Person(name=u'lvh', storeID=3)@..., Person(name=u'pydanny', storeID=2)@...]

Additionally, there's a super secret club for people who like
pistachio flavored ice cream. Only lvh likes pistachio ice cream. If
we want to query all the people who *don't*, we'd use ``notOneOf``:

.. doctest::

   >>> doesNotLikePistachio = Person.name.notOneOf([u"lvh"])
   >>> list(store.query(Person, doesNotLikePistachio, sort=Person.name.ascending))
   [Person(name=u'audreyr', storeID=1)@..., Person(name=u'pydanny', storeID=2)@...]

And that's all there is to it.

``notOneOf`` and ``oneOf`` are supported by almost all attributes,
except ``inmemory``. That said, comparing floats (``ieee754_double``)
is probably not what you wanted -- but that's inherent to floats, not
anything specific to Axiom.
