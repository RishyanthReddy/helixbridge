import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from binder_campaign.runner import digest
from binder_campaign.staging import extract_verified, tree_members


class StagingTests(unittest.TestCase):
    def test_round_trip_and_changed_archive_or_member_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source'
            (source / 'nested').mkdir(parents=True)
            (source / 'nested/data').write_bytes(b'fixed scientific input')
            archive = root / 'source.tar'
            with tarfile.open(archive, 'w') as package:
                package.add(source / 'nested', arcname='nested')
            description = {'bytes': archive.stat().st_size, 'sha256': digest(archive),
                           'members': tree_members(source)}
            extract_verified(archive, root / 'restored', description)
            self.assertEqual((root / 'restored/nested/data').read_bytes(), b'fixed scientific input')
            description['members']['nested/data']['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'Staged file'):
                extract_verified(archive, root / 'bad-member', description)
            description['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'Archive digest'):
                extract_verified(archive, root / 'bad-archive', description)

    def test_parent_escape_and_external_symlink_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / 'bad.tar'
            with tarfile.open(archive, 'w') as package:
                entry = tarfile.TarInfo('../escaped')
                entry.size = 4
                package.addfile(entry, io.BytesIO(b'data'))
            with self.assertRaisesRegex(ValueError, 'Unsafe archive'):
                extract_verified(archive, root / 'target', {'bytes': archive.stat().st_size,
                    'sha256': digest(archive), 'members': {}})
            self.assertFalse((root / 'escaped').exists())
            source = root / 'source'
            source.mkdir()
            (source / 'external').symlink_to(root / 'outside')
            with self.assertRaises(ValueError):
                tree_members(source)
