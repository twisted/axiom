"""
Hypothesis strategies for generating Axiom-related data.
"""
from epsilon.extime import Time
from hypothesis import strategies as st
from hypothesis.extra.datetime import datetimes

from axiom.attributes import LARGEST_NEGATIVE, LARGEST_POSITIVE



def axiom_text(*a, **kw):
    """
    Strategy for generating Axiom-compatible text values.
    """
    return st.text(
        alphabet=st.characters(
            blacklist_categories={'Cs'},
            blacklist_characters={u'\x00'}),
        *a, **kw)



def axiom_integers():
    """
    Strategy for generating Axiom-compatible integers.
    """
    return st.integers(min_value=LARGEST_NEGATIVE, max_value=LARGEST_POSITIVE)



def timestamps():
    """
    Strategy for generating L{epsilon.extime.Time} objects.
    """
    return st.builds(Time.fromDatetime, datetimes(timezones=[]))



__all__ = ['axiom_text', 'axiom_integers', 'timestamps']
