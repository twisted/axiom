
from pysqlite2.dbapi2 import connect as opendb

con = opendb("test.sqlite")
cur = con.cursor()
