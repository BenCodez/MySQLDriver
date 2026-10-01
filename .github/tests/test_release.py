import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PREPARE = runpy.run_path(str(ROOT / '.github/scripts/prepare-release.py'))
PUBLISH = ROOT / '.github/scripts/publish-release.sh'
COMMIT = 'a' * 40


class PrepareReleaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        (self.project / 'target').mkdir()
        (self.project / 'pom.xml').write_text(
            '<project xmlns="http://maven.apache.org/POM/4.0.0"><version>1.0</version></project>'
        )
        self.entries = {entry: b'bytecode' for entry in PREPARE['PLUGIN_CLASSES']}
        self.entries.update({name.replace('.', '/') + '.class': b'bytecode' for name in PREPARE['DRIVERS']})
        self.entries.update({
            'META-INF/services/java.sql.Driver': '\n'.join(PREPARE['DRIVERS']).encode(),
            'plugin.yml': b'name: MySQLDriver\nversion: 1.0\n',
            'bungee.yml': b'name: MySQLDriver\nversion: "1.0"\n',
            'velocity-plugin.json': b'{"id":"mysqldriver","version":"1.0"}',
        })

    def prepare(self, tag='v1.0'):
        with zipfile.ZipFile(self.project / 'target/MySQLDriver.jar', 'w') as jar:
            for name, data in self.entries.items():
                jar.writestr(name, data)
        return PREPARE['prepare'](self.project, tag)

    def test_preserves_jar_bytes_and_checksums(self):
        artifact = self.prepare()
        self.assertEqual(artifact.name, 'MySQLDriver-1.0.jar')
        self.assertEqual(artifact.read_bytes(), (self.project / 'target/MySQLDriver.jar').read_bytes())
        self.assertEqual(artifact.with_suffix('.jar.sha256').read_text(),
                         hashlib.sha256(artifact.read_bytes()).hexdigest() + '  MySQLDriver-1.0.jar\n')

    def test_branch_build_checks_assets_without_a_tag(self):
        self.assertTrue(self.prepare('').is_file())

    def test_mismatched_or_unsafe_tags_are_rejected(self):
        for tag in ('v1.1', '1.0', 'v1.0-rc1', 'v1.0/../../asset'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.prepare(tag)
        self.assertFalse((self.project / 'target/release').exists())

    def test_missing_driver_and_entrypoint_are_rejected(self):
        for entry in ('org/postgresql/Driver.class', PREPARE['PLUGIN_CLASSES'][0]):
            saved = self.entries.pop(entry)
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                self.prepare()
            self.entries[entry] = saved

    def test_missing_service_provider_is_rejected(self):
        self.entries['META-INF/services/java.sql.Driver'] = b'com.mysql.cj.jdbc.Driver\n'
        with self.assertRaises(ValueError):
            self.prepare()

    def test_descriptor_versions_must_match(self):
        for entry, bad in (('plugin.yml', b'version: 1.1\n'),
                           ('bungee.yml', b'version: 1.1\n'),
                           ('velocity-plugin.json', b'{"version":"1.1"}')):
            saved = self.entries[entry]
            self.entries[entry] = bad
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                self.prepare()
            self.entries[entry] = saved

    def test_stale_output_is_rejected(self):
        self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare()


class PublishReleaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        jar = self.directory / 'MySQLDriver-1.0.jar'
        jar.write_bytes(b'exact-build-output')
        jar.with_suffix('.jar.sha256').write_text(hashlib.sha256(jar.read_bytes()).hexdigest() + '  ' + jar.name + '\n')
        self.log = self.directory / 'calls.jsonl'
        self.stub = self.directory / 'gh'
        self.stub.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
log = Path(os.environ['CALL_LOG'])
previous = log.read_text().splitlines() if log.exists() else []
with log.open('a') as stream:
    stream.write(json.dumps(args) + '\\n')
mode = os.environ.get('TEST_MODE', '')
if args[0] == 'api' and '--paginate' in args:
    if mode == 'lookup_failure':
        sys.exit(1)
    if mode in ('existing_draft', 'existing_published'):
        print('42')
elif args[0] == 'api':
    if mode == 'missing_tag':
        sys.exit(1)
    moved = mode == 'moved_tag' or (mode == 'tag_moved_after_upload' and len(previous) > 2)
    print('b' * 40 if moved else 'a' * 40)
elif args[:2] == ['release', 'create']:
    if mode == 'upload_failure':
        sys.exit(1)
elif args[:2] != ['release', 'edit']:
    sys.exit('Unexpected command')
''')
        self.stub.chmod(0o755)

    def run_publish(self, mode='', **overrides):
        env = dict(os.environ, PATH=str(self.directory) + os.pathsep + os.environ['PATH'],
                   CALL_LOG=str(self.log), TEST_MODE=mode, GH_REPO='owner/repo',
                   RELEASE_TAG='v1.0', RELEASE_COMMIT=COMMIT)
        env.update(overrides)
        result = subprocess.run(['bash', str(PUBLISH), str(self.directory)], env=env,
                                capture_output=True, text=True, timeout=10)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result, calls

    def test_success_uploads_both_assets_as_draft_before_publish(self):
        result, calls = self.run_publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([args[0] for args in calls], ['api', 'api', 'release', 'api', 'release'])
        create = calls[2]
        self.assertEqual(create[:5], ['release', 'create', 'v1.0', 'MySQLDriver-1.0.jar', 'MySQLDriver-1.0.jar.sha256'])
        self.assertIn('--draft', create)
        self.assertIn('--verify-tag', create)
        self.assertIn('--draft=false', calls[-1])
        self.assertNotIn('--clobber', str(calls))

    def test_existing_releases_and_read_errors_cannot_publish(self):
        for mode in ('existing_draft', 'existing_published', 'lookup_failure', 'missing_tag', 'moved_tag'):
            self.log.unlink(missing_ok=True)
            result, calls = self.run_publish(mode)
            with self.subTest(mode=mode):
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(args[0] == 'release' for args in calls))

    def test_failed_upload_and_moved_tag_leave_draft_unpublished(self):
        for mode in ('upload_failure', 'tag_moved_after_upload'):
            self.log.unlink(missing_ok=True)
            result, calls = self.run_publish(mode)
            with self.subTest(mode=mode):
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(any(args[:2] == ['release', 'create'] for args in calls))
                self.assertFalse(any(args[:2] == ['release', 'edit'] for args in calls))

    def test_checksum_mismatch_stops_before_remote_writes(self):
        (self.directory / 'MySQLDriver-1.0.jar').write_bytes(b'changed-build-output')
        result, calls = self.run_publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_invalid_tag_stops_before_api_access(self):
        result, calls = self.run_publish(RELEASE_TAG='v1.0/unsafe')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])
