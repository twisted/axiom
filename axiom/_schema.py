
DELETE_OBJECT = 'DELETE FROM axiom_objects WHERE oid = ?'
CREATE_OBJECT = 'INSERT INTO axiom_objects (type_id) VALUES (?)'
CREATE_TYPE = 'INSERT INTO axiom_types (typename, version) VALUES (?, ?)'


BASE_SCHEMA = ["""
CREATE TABLE axiom_objects (
    type_id INTEGER NOT NULL
        CONSTRAINT fk_type_id REFERENCES axiom_types(oid)
)
""",

"""
CREATE TABLE axiom_types (
    typename VARCHAR(256),
    version INTEGER
)
""",

"""
CREATE TABLE axiom_attributes (
    type_id INTEGER,
    row_offset INTEGER,
    indexed BOOLEAN,
    sqltype VARCHAR,
    pythontype VARCHAR,
    attribute VARCHAR,
    docstring TEXT
)
"""]

TYPEOF_QUERY = """
SELECT axiom_types.typename, axiom_types.version
    FROM axiom_types, axiom_objects
    WHERE axiom_objects.oid = ?
        AND axiom_types.oid = axiom_objects.type_id
"""

HAS_SCHEMA_FEATURE = ("SELECT COUNT(oid) FROM sqlite_master "
                      "WHERE type = ? AND name = ?")

IDENTIFYING_SCHEMA = ('SELECT indexed, sqltype, attribute '
                      'FROM axiom_attributes WHERE type_id = ? '
                      'ORDER BY row_offset')

ADD_SCHEMA_ATTRIBUTE = (
    'INSERT INTO axiom_attributes '
    '(type_id, row_offset, indexed, sqltype, attribute, docstring, pythontype) '
    'VALUES (?, ?, ?, ?, ?, ?, ?)')

ALL_TYPES = 'SELECT oid, typename, version FROM axiom_types'

GET_TYPE_OF_VERSION = ('SELECT version FROM axiom_types '
                       'WHERE typename = ? AND version > ? -- get type of version')

SCHEMA_FOR_TYPE = ('SELECT indexed, pythontype, attribute, docstring '
                   'FROM axiom_attributes '
                   'WHERE type_id = ?')

CHANGE_TYPE = 'UPDATE axiom_objects SET type_id = ? WHERE oid = ?'

