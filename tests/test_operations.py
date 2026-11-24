"""Offline safeguards for deployment utilities; never invokes Docker."""
import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest

def load(name, tmp_path, monkeypatch, arguments):
    script=Path(__file__).resolve().parent.parent/'scripts'/f'{name}.py'
    spec=importlib.util.spec_from_file_location('ops_'+name,script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'ROOT',tmp_path)
    monkeypatch.setattr('sys.argv',[str(script),*arguments])
    return module

def test_preflight_refuses_missing_configuration(tmp_path,monkeypatch):
    module=load('preflight',tmp_path,monkeypatch,[])
    with pytest.raises(SystemExit,match='Missing .env'):module.main()

def test_preflight_refuses_invalid_encryption_key(tmp_path,monkeypatch):
    (tmp_path/'.env').write_text('ADMIN_EMAIL=a@example.com\nADMIN_PASSWORD=long-password-123\nPOSTGRES_PASSWORD=abcdef\nSETTINGS_ENCRYPTION_KEY=wrong\n')
    module=load('preflight',tmp_path,monkeypatch,[])
    with pytest.raises(SystemExit,match='Invalid settings encryption key'):module.main()

def test_backup_writes_valid_dump_and_refuses_overwrite(tmp_path,monkeypatch):
    out=tmp_path/'safe.dump';module=load('backup',tmp_path,monkeypatch,['--output',str(out)])
    def run(command,**kw):
        assert command[-1]=='-Fc' and 'pg_dump' in command
        kw['stdout'].write(b'PGDMP-example');return SimpleNamespace(returncode=0)
    monkeypatch.setattr(module.subprocess,'run',run);module.main()
    assert out.read_bytes()==b'PGDMP-example'
    with pytest.raises(SystemExit,match='Output exists'):module.main()

def test_failed_backup_removes_partial_output(tmp_path,monkeypatch):
    out=tmp_path/'failed.dump';module=load('backup',tmp_path,monkeypatch,['--output',str(out)])
    monkeypatch.setattr(module.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=1))
    with pytest.raises(RuntimeError,match='pg_dump failed'):module.main()
    assert not out.exists() and not out.with_name('failed.dump.partial').exists()

def test_backup_preserves_another_writers_partial_file(tmp_path,monkeypatch):
    out=tmp_path/'active.dump';partial=tmp_path/'active.dump.partial';partial.write_bytes(b'other-backup-in-progress')
    module=load('backup',tmp_path,monkeypatch,['--output',str(out)])
    with pytest.raises(FileExistsError):module.main()
    assert partial.read_bytes()==b'other-backup-in-progress'

def test_restore_refuses_populated_database(tmp_path,monkeypatch):
    dump=tmp_path/'safe.dump';dump.write_bytes(b'PGDMP-example')
    module=load('restore',tmp_path,monkeypatch,[str(dump),'--project-name','recovery','--confirm-empty-restore']);calls=[]
    def run(command,**kw):
        calls.append(command)
        return SimpleNamespace(returncode=0,stdout='db\n' if 'ps' in command else '5\n')
    monkeypatch.setattr(module.subprocess,'run',run)
    with pytest.raises(SystemExit,match='not empty'):module.main()
    assert not any('pg_restore' in command for command in calls)

def test_restore_quarantines_integrations_and_leaves_app_stopped(tmp_path,monkeypatch):
    dump=tmp_path/'safe.dump';dump.write_bytes(b'PGDMP-example')
    module=load('restore',tmp_path,monkeypatch,[str(dump),'--project-name','recovery','--confirm-empty-restore']);calls=[]
    def run(command,**kw):
        calls.append(command)
        return SimpleNamespace(returncode=0,stdout='db\n' if 'ps' in command else '0\n')
    monkeypatch.setattr(module.subprocess,'run',run);module.main()
    restore=next(command for command in calls if 'pg_restore' in command)
    assert '--single-transaction' in restore and '--clean' not in restore
    assert any('jsonb_set' in command[-1] and 'retrieval' in command[-1] for command in calls)
    assert not any(command[-1] in {'app','worker'} for command in calls)
