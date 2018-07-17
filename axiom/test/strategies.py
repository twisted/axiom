"""
Hypothesis strategies for generating Axiom-related data.
"""
from epsilon.extime import Time
from hypothesis import strategies as st
from hypothesis.extra.datetime import datetimes

from axiom.attributes import LARGEST_NEGATIVE, LARGEST_POSITIVE



def axiomText(*a, **kw):
    """
    Strategy for generating Axiom-compatible text values.
    """
    return st.text(
        alphabet=st.characters(
            blacklist_categories={'Cs'},
            blacklist_characters={u'\x00'}),
        *a, **kw)


def textlists():
    """
    Strategy for generating lists storable with L{axiom.attributes.textlist}.
    """
    return st.lists(st.text(
        alphabet=st.characters(
            blacklist_categories={'Cs'},
            blacklist_characters={u'\x00', u'\x02', u'\x1f'})))



def axiomIntegers(minValue=LARGEST_NEGATIVE, maxValue=LARGEST_POSITIVE):
    """
    Strategy for generating Axiom-compatible integers.

    @type minValue: L{int}
    @param minValue: Minimum value to generate; default is the least value
        that can be stored in an L{axiom.attributes.integer} attribute.

    @type manValue: L{int}
    @param manValue: Maximum value to generate; default is the greatest value
        that can be stored in an L{axiom.attributes.integer} attribute.
    """
    return st.integers(min_value=minValue, max_value=maxValue)



def timestamps(*a, **kw):
    """
    Strategy for generating L{epsilon.extime.Time} objects.
    """
    return st.builds(Time.fromDatetime, datetimes(timezones=[], *a, **kw))



def fixedDecimals(precision, minValue=None, maxValue=None):
    """
    Strategy for generating L{decimal.Decimal} values of a fixed precision.

    @type precision: L{decimal.Decimal}
    @param precision: The precision to use; for example, C{Decimal('0.01')} for
        a L{axiom.attributes.point2decimal} attribute.

    @type minValue: L{decimal.Decimal}
    @param minValue: The minimum value to generate, or C{None} for the least
        possible.
    @type minValue: L{decimal.Decimal}
    @param minValue: The maximum value to generate, or C{None} for the greatest
        possible.
    """
    if minValue is None:
        minValue = LARGEST_NEGATIVE
    else:
        minValue = int(minValue / precision)
    if maxValue is None:
        maxValue = LARGEST_POSITIVE
    else:
        maxValue = int(maxValue / precision)
    return st.integers(min_value=minValue, max_value=maxValue).map(
        lambda v: v * precision)



__all__ = [
    'axiomText', 'axiomIntegers', 'fixedDecimals', 'timestamps', 'textlists']
