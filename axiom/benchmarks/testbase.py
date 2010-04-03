
from axiom._pysqlite2 import Connection

con = Connection.fromDatabaseName("test.sqlite")
cur = con.cursor()
