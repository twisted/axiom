
import random

from axiom.item import Item
from axiom.attributes import text, timestamp, reference, integer, AND, OR
from axiom.store import Store
from epsilon import extime

_d = extime.Time.fromISO8601TimeAndDate

_books = [
    (u'Heart of Darkness', u'Joseph Conrad', u'0486264645', 80, _d('1990-07-01T00:00:00.000001')),
    (u'The Dark Tower, Book 7', u'Stephen King', u'1880418622', 864, _d('2004-11-21T00:00:00.000001')),
    (u'Guns, Germs, and Steel: The Fates of Human Societies', u'Jared Diamond', u'0393317552', 480, _d('1999-04-01T00:00:00.000001')),
    (u'The Lions of al-Rassan', u'Guy Gavriel Kay', u'0060733497', 528, _d('2005-06-28T00:00:00.000001')),
    ]

_borrowers = [u'Anne', u'Bob', u'Carol', u'Dave']


class Borrower(Item):
    typeName = 'borrower'
    schemaVersion = 1
    name = text(indexed=True)

class Book(Item):
    typeName = 'book'
    schemaVersion = 1

    title = text()
    author = text()
    isbn = text()
    pages = integer()
    datePublished = timestamp()

    lentTo = reference()
    library = reference()

class LendingLibrary(Item):
    typeName = 'lending_library'
    schemaVersion = 1

    name = text()

    def books(self):
        return self.store.query(Book,
                                Book.library == self)

    def getBorrower(self, name):
        for b in self.store.query(Borrower,
                                  Borrower.name == name):
            return b
        b = Borrower(name=name,
                     store=self.store)
        return b

    def initialize(self):
        for title, author, isbn, pages, published in _books:
            b = Book(
                title=title,
                author=author,
                isbn=isbn,
                pages=pages,
                datePublished=published,
                library=self,
                store=self.store)


    def displayBooks(self):
        for book in self.books():
            print book.title,
            if book.lentTo is not None:
                print 'lent to', '['+book.lentTo.name+']'
            else:
                print 'in library'

    def shuffleLending(self):
        for book in self.books():
            if book.lentTo is not None:
                print book.lentTo.name, 'returned', book.title
                book.lentTo = None
        for book in self.books():
            if random.choice([True, False]):
                borrower = random.choice(_borrowers)
                print 'Lending', book.title, 'to', borrower
                book.lentTo = self.getBorrower(borrower)

def main(s):
    for ll in s.query(LendingLibrary):
        print 'found existing library'
        break
    else:
        print 'creating new library'
        ll = LendingLibrary(store=s)
        ll.initialize()
    ll.displayBooks()
    print '***'
    ll.shuffleLending()
    print '---'
    ll.displayBooks()
    print '***'
    ll.shuffleLending()
    print '---'

    print s.count(Book, AND (Book.author == u'Stephen King',
                             Book.title == u'The Lions of al-Rassan'))
    print s.count(Book, OR (Book.author == u'Stephen King',
                            Book.title == u'The Lions of al-Rassan'))


if __name__ == '__main__':
    s = Store('testdb')
    s.transact(main, s)
    s.close()
