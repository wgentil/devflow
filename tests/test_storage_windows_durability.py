"""Durability flushes require write-capable handles on native Windows."""
from contextlib import contextmanager
import errno
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib import sqlite_store,store
from workflow_lib.storage_backups import sqlite_backup
from workflow_lib.storage_format import DATABASE_FILE

@contextmanager
def write_capable_flushes():
    # Real files/SQLite; emulate only the documented Windows flush access rule.
    opened={};original_open=Path.open;original_sync=os.fsync
    def open_file(path,*args,**kwargs):
        handle=original_open(path,*args,**kwargs);opened[handle.fileno()]=handle
        return handle
    def sync(fd):
        handle=opened.get(fd)
        if handle is not None and not handle.closed and not handle.writable():
            raise OSError(errno.EBADF,'Windows flush requires a write-capable handle')
        return original_sync(fd)
    with patch.object(Path,'open',open_file),patch.object(os,'fsync',sync):yield

class WindowsStorageDurabilityTests(unittest.TestCase):
    def test_initialization_flush_preserves_a_valid_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'control é東京'
            with write_capable_flushes():sqlite_store.initialize_store(root)
            with sqlite_store.connection(root) as conn:
                self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(sqlite_store._meta(conn,'head'),0)

    def test_backup_flush_preserves_complete_sqlite_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'control';sqlite_store.initialize_store(root)
            store.transact(root,0,'preserved',{'kind':'note','payload':{'value':'é東京'}})
            target=Path(temporary)/'backup é東京.sqlite3'
            with write_capable_flushes():sqlite_backup(root/DATABASE_FILE,target)
            conn=sqlite_store._sqlite().connect(target)
            try:
                self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(sqlite_store._meta(conn,'root_id'),sqlite_store.detect_layout(root)['root_id'])
                state=sqlite_store._read_view(conn,root,sqlite_store.ReadScope(full=True))[0]
                self.assertEqual(state['version'],1)
                self.assertEqual(state['data']['value'],'é東京')
            finally:conn.close()
