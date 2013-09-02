==========
 Powerups
==========

Powerups are a fairly unique feature to Axiom. They provide a way of
persisting adapters to interfaces.

Powerups are built on top of Zope interfaces. If you don't know what
they are, the short version is that they're objects that describe the
*API* of other objects, without having any particular implementation.

Adaptation
==========

Adaptation is a feature that's present in several libraries, such as
Twisted. Let's say that you want an object satisfying the ``IMailer``
interface (an interface for objects that allow you to send e-mail),
and you currently have a user object. Perhaps you could get an object
that would let you send e-mail to a particular user by doing:


.. code-block:: python

    mailer = IMailer(user)

The basic idea that you can adapt an object to some interface, by
calling the interface with that object, to get a (usually different)
object that satisfies the interface you want.

Axiom provides adaptation in the form of powerups. Powerups allow you
to easily persist objects with pretty much arbitrary behavior and
allow you to add them to existing objects, without modifying them.

Adding powerups
===============

For this example, we'll create transformers that can turn into cars.
First, we'll define the interfaces: that is, we define what you can do
with robot and car objects:

.. literalinclude:: transformers.py
    :pyobject: IRobot

.. literalinclude:: transformers.py
    :pyobject: ICar

We make two sample implementations:

.. literalinclude:: transformers.py
    :pyobject: Transformer

.. literalinclude:: transformers.py
    :pyobject: Truck

When you create just any ``Transformer``, it can't automagically turn
into a car yet (that is, it's not adaptable to ``ICar``). When you try
to adapt it, an error is raised:

.. testsetup::

    from axiom.store import Store
    from transformers import ICar, IRobot, Transformer, Truck, HotRod

.. doctest::

    >>> store = Store()
    >>> optimus = Transformer(store=store, name=u"Optimus Prime", damage=100)
    >>> ICar(optimus)
    Traceback (most recent call last):
    ...
    TypeError: ('Could not adapt', ...)

The store is required because powerups are persisted.

If you can turn any arbitrary ``IRobot`` into any ``ICar``, you want a
regular adapter registry, such as the one offered by Twisted. In this
case, we want to make it so that this particular transformer can turn
into a car. Additionally, we want that behavior to be persisted. To do
this, we'll be installing a powerup on the item:

.. doctest::

    >>> truck = Truck(store=store, wheels=8)
    >>> optimus.powerUp(truck, ICar)

After that, we can adapt the transformer to be a car:

.. doctest::

    >>> assert ICar(optimus) is truck

In-memory powerups
==================

Sometimes, particularly while experimenting or testing, it may be
useful to use in-memory powerups instead of regular powerups. These
are not persisted, and die whenever the object dies.

.. doctest::

    >>> inMemory = Store()
    >>> rodimus = Transformer(store=inMemory, name=u"Rodimus Prime", damage=50)
    >>> hotRod = HotRod(store=inMemory, color=u"Red and yellow")
    >>> rodimus.inMemoryPowerUp(hotRod, ICar)
    >>> assert ICar(rodimus) is hotRod

Removing powerups
=================

Powerups can be removed by the ``powerDown`` method.

.. doctest::

    >>> optimus.powerDown(truck, ICar)
    >>> ICar(optimus)
    Traceback (most recent call last):
    ...
    TypeError: ('Could not adapt', ...)

(Since it's a crying shame that Optimus can't turn into a truck, we'll
restore his abilities.)

.. doctest::

    >>> optimus.powerUp(truck, ICar)
    >>> assert ICar(optimus) is truck
