# Copyright 2008 Divmod, Inc.  See LICENSE for details.

"""
Test for the deletion of L{BatchManholePowerup}.
"""

from axiom.batch import BatchManholePowerup
from axiom.test.historic.stubloader import StubbedTest


class BatchManholePowerupTests(StubbedTest):
    def test_deletion(self):
        """
        The upgrade to schema version 2 deletes L{BatchManholePowerup}.
        """
        self.assertEqual(self.store.query(BatchManholePowerup).count(), 0)
