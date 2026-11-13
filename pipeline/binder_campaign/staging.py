"""Content-verified extraction of trusted, CPU-prepared runtime archives."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import tarfile

from .runner import digest


def validate_member_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('Unsafe archive path: ' + name)
    return path


def tree_members(root):
    """Describe every file/link; refuse external links instead of copying secrets."""
    root = Path(root).resolve()
    members = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(parent) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                path.resolve().relative_to(root)
                members[relative] = {'type': 'symlink', 'target': os.readlink(path)}
            elif path.is_file():
                members[relative] = {'type': 'file', 'bytes': path.stat().st_size, 'sha256': digest(path)}
    return dict(sorted(members.items()))


def verify_members(root, members):
    root = Path(root).resolve()
    for name, expected in members.items():
        validate_member_name(name)
        path = root / name
        if expected['type'] == 'symlink':
            if not path.is_symlink() or os.readlink(path) != expected['target']:
                raise ValueError('Staged symlink changed: ' + name)
            path.resolve().relative_to(root)
        elif expected['type'] == 'file':
            if path.is_symlink() or not path.is_file() or path.stat().st_size != expected['bytes'] \
                    or digest(path) != expected['sha256']:
                raise ValueError('Staged file changed: ' + name)
        else:
            raise ValueError('Unsupported member type')


class HashReader:
    def __init__(self, stream):
        self.stream = stream
        self.hash = hashlib.sha256()

    def read(self, size=-1):
        data = self.stream.read(size)
        self.hash.update(data)
        return data


def extract_verified(archive, destination, description):
    """One source pass: extract with data filters and hash the entire archive."""
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Staging destination already exists')
    if Path(archive).stat().st_size != description['bytes']:
        raise ValueError('Archive size changed')
    destination.mkdir(parents=True)
    with open(archive, 'rb') as source:
        reader = HashReader(source)
        with tarfile.open(fileobj=reader, mode='r|') as package:
            for member in package:
                validate_member_name(member.name)
                if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                    raise ValueError('Unsupported archive entry')
                package.extract(member, path=destination, filter='data')
        while reader.read(1024 * 1024):
            pass
        if reader.hash.hexdigest() != description['sha256']:
            raise ValueError('Archive digest changed')
    verify_members(destination, description['members'])
    return {'archive_sha256': description['sha256'], 'verified_members': len(description['members'])}
