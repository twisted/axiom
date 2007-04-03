
from axiom.test.historic.stubloader import StubbedTest
from axiom.test.historic.stub_textlist import Dummy

class TextlistTransitionTest(StubbedTest):
    def test_transition(self):
        """
        Test that the textlist survives the encoding transition intact.
        """
        d = self.store.findUnique(Dummy)
        self.assertEquals(d.attribute, [u'foo', u'bar'])
