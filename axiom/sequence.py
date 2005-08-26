# -*- test-case-name: axiom.test.test_sequence -*-

from axiom.item import Item

from axiom.attributes import reference, integer, AND

class _ListItem(Item):
    typeName = 'list_item'
    schemaVersion = 1

    _index = integer()
    _value = reference()
    _container = reference()

class List(Item):

    typeName = 'list'
    schemaVersion = 1

    length = integer(default=0)

    def _getListItem(self, index):
        assert isinstance(index, int)
        if index < 0:
            index += self.length
        if index < 0 or index >= self.length:
            raise IndexError("stored list index out of range")
        return list(self.store.query(_ListItem,
                                     AND(_ListItem._container == self,
                                         _ListItem._index == index)))[0]

    def __getitem__(self, index):
        return self._getListItem(index)._value

    def __setitem__(self, index, value):
        self._getListItem(index)._value = value

    def append(self, value):
        _ListItem(store=self.store,
                  _value=value,
                  _container=self,
                  _index=self.length)
        self.length += 1

