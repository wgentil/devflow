"""Independent, point-verifiable entity discovery witnesses (not authentication)."""
from .store import WorkflowError

SCHEMA='''
CREATE TABLE entity_catalog(space TEXT, key TEXT,
    position INTEGER NOT NULL, value_hash TEXT NOT NULL, run_id TEXT, status TEXT,
    host TEXT, session_id TEXT, package_hash TEXT, record_id TEXT, PRIMARY KEY(space,key));
CREATE INDEX catalog_run ON entity_catalog(space,run_id);
CREATE INDEX catalog_status ON entity_catalog(space,status);
CREATE INDEX catalog_session ON entity_catalog(space,host,session_id,status);
CREATE INDEX catalog_identity ON entity_catalog(space,record_id);
'''
FIELDS='position,value_hash,run_id,status,host,session_id,package_hash,record_id'


def headers(path,value):
    meta=value if isinstance(value,dict) else {}
    binding=meta.get('binding') if isinstance(meta.get('binding'),dict) else {}
    run_id=meta.get('run_id') or (binding.get('run_id') if path==('usage','events') else meta.get('id') if path==('runs',) else None)
    # Query headers are auxiliary strings; opaque legacy business values retain
    # their original types in the checksum-bound body, including unknown shapes.
    def text(value):
        if isinstance(value,str) or value is None:return value
        if isinstance(value,bool):return str(int(value))
        if isinstance(value,(int,float)):return str(value)
        return None
    return tuple(text(value) for value in (run_id,meta.get('status'),meta.get('host'),meta.get('session_id'),meta.get('package_hash'),meta.get('id')))


def sync(conn,fields):
    values=fields[:3]+(fields[5],)+fields[6:]
    conn.execute('''INSERT INTO entity_catalog VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(space,key) DO UPDATE SET
        position=excluded.position,value_hash=excluded.value_hash,run_id=excluded.run_id,status=excluded.status,
        host=excluded.host,session_id=excluded.session_id,package_hash=excluded.package_hash,record_id=excluded.record_id''',values)


def check(conn,space,key,*,path=None,value=None):
    actual=conn.execute('SELECT '+FIELDS+' FROM entities WHERE space=? AND key=?',(space,key)).fetchone()
    witness=conn.execute('SELECT '+FIELDS+' FROM entity_catalog WHERE space=? AND key=?',(space,key)).fetchone()
    if actual!=witness or path is not None and actual is not None and actual[2:]!=headers(path,value):
        raise WorkflowError('CORRUPT_STORAGE','Entity catalog/header differs from its authoritative record; preserve the root and run full verification.')
    return actual


def rows(conn,space,filters=()):
    allowed={'run_id','status','host','session_id','package_hash','record_id','key'}
    if any(field not in allowed for field,_ in filters):
        raise WorkflowError('UNDECLARED_STORAGE_SCOPE','An unindexed query is not an operational scope.')
    where=''.join(' AND '+field+'=?' for field,_ in filters)
    selected='SELECT key FROM entity_catalog WHERE space=?'+where+' UNION SELECT key FROM entities WHERE space=?'+where
    values=(space,*(value for _,value in filters))
    return conn.execute('SELECT chosen.key,e.codec,e.payload,e.value_hash FROM ('+selected+''' ) chosen
        LEFT JOIN entities e ON e.space=? AND e.key=chosen.key ORDER BY e.position''',
        (*values,*values,space)).fetchall()


def delete_space(conn,space):
    # Witnesses deliberately do not cascade from authority: a damaged namespace
    # must leave evidence. Intended removals update both copies in one transaction.
    conn.execute('''WITH RECURSIVE selected(path) AS (
        SELECT ? UNION SELECT s.path FROM spaces s JOIN selected p ON s.parent=p.path)
        DELETE FROM entity_catalog WHERE space IN (SELECT path FROM selected)''',(space,))
    conn.execute('DELETE FROM spaces WHERE path=?',(space,))



def verify(conn):
    if conn.execute('SELECT 1 FROM entity_catalog c LEFT JOIN spaces s ON s.path=c.space WHERE s.path IS NULL LIMIT 1').fetchone():
        raise WorkflowError('CORRUPT_STORAGE','Entity namespace is missing while its independent catalog witness remains.')
    columns='space,key,'+FIELDS
    # Explicit full audit may enumerate both catalogs. Operational reads never do.
    if conn.execute('SELECT '+columns+' FROM entities EXCEPT SELECT '+columns+' FROM entity_catalog').fetchone() or conn.execute('SELECT '+columns+' FROM entity_catalog EXCEPT SELECT '+columns+' FROM entities').fetchone():
        raise WorkflowError('CORRUPT_STORAGE','Complete entity catalog differs from current records; no history was restored.')
