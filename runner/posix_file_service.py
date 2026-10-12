"""A provider-specific POSIX file adapter, observer, and commit harness.

The harness maps the virtual ``/workspace`` namespace into a temporary
directory.  The secure path walks parent directories with directory file
descriptors, rejects symlinks, checks the authorized parent identity at commit,
and creates the target exclusively.  The naive path uses an absolute pathname
for the comparison baseline.  Neither path touches a user directory.
"""

from __future__ import annotations

from dataclasses import dataclass
import errno
import hashlib
import os
from pathlib import Path
import stat
from typing import Iterable


VIRTUAL_ROOT = "/workspace"
AUTHORIZED_PREFIX = "/workspace/session/notes"


@dataclass(frozen=True)
class FileCandidate:
    virtual_path: str
    content: str
    content_digest: str


@dataclass(frozen=True)
class ParentSnapshot:
    virtual_parent: str
    device: int
    inode: int
    resolved_parent: str


@dataclass(frozen=True)
class FileObservation:
    label: str
    reason: str
    virtual_path: str
    resolved_path: str
    content_digest: str
    link_count: int
    parent_changed: bool
    outside_authorized_namespace: bool


@dataclass(frozen=True)
class CommitResult:
    decision: str
    reason: str
    committed: bool


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parts(virtual_path: str) -> tuple[str, ...]:
    if not isinstance(virtual_path, str) or not virtual_path.startswith("/workspace/"):
        raise ValueError("path must be under /workspace")
    parts = tuple(virtual_path.split("/")[2:])
    if not parts or any(not item or item in {".", ".."} for item in parts):
        raise ValueError("path contains an unsupported component")
    return parts


def _is_below(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


class PosixFileSandbox:
    """Temporary provider namespace used by one independent audit trial."""

    def __init__(self, root: Path):
        self.root = root
        self.workspace = root / "workspace"
        self.session = self.workspace / "session"
        self.notes = self.session / "notes"
        self.startup = self.workspace / "startup"
        self.autoload = self.workspace / "autoload"
        for directory in (self.notes, self.startup, self.autoload):
            directory.mkdir(parents=True, exist_ok=True)
        self.commit_count = 0

    def host_path(self, virtual_path: str) -> Path:
        return self.workspace.joinpath(*_parts(virtual_path))

    @staticmethod
    def candidate(virtual_path: str, content: str) -> FileCandidate:
        _parts(virtual_path)
        if not isinstance(content, str):
            raise ValueError("content must be text")
        payload = content.encode("utf-8")
        return FileCandidate(virtual_path, content, _digest(payload))

    def _open_dir_chain(self, components: Iterable[str]) -> int:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open(self.workspace, directory_flags)
        try:
            for component in components:
                next_fd = os.open(component, directory_flags, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            return fd
        except Exception:
            os.close(fd)
            raise

    def prepare(self, candidate: FileCandidate) -> ParentSnapshot:
        parts = _parts(candidate.virtual_path)
        parent = "/".join((VIRTUAL_ROOT, *parts[:-1]))
        fd = self._open_dir_chain(parts[:-1])
        try:
            info = os.fstat(fd)
            resolved_parent = str(self.host_path(candidate.virtual_path).parent.resolve())
            return ParentSnapshot(
                parent,
                int(info.st_dev),
                int(info.st_ino),
                resolved_parent,
            )
        finally:
            os.close(fd)

    def _parent_matches(self, fd: int, snapshot: ParentSnapshot) -> bool:
        info = os.fstat(fd)
        return int(info.st_dev) == snapshot.device and int(info.st_ino) == snapshot.inode

    def secure_commit(
        self,
        candidate: FileCandidate,
        snapshot: ParentSnapshot,
        *,
        max_commits: int = 1,
    ) -> CommitResult:
        if self.commit_count >= max_commits:
            return CommitResult(
                "block",
                f"sequence cardinality exceeds grant {max_commits}",
                False,
            )
        parts = _parts(candidate.virtual_path)
        parent_fd = -1
        target_fd = -1
        try:
            parent_fd = self._open_dir_chain(parts[:-1])
            if not self._parent_matches(parent_fd, snapshot):
                return CommitResult(
                    "block",
                    "authorized parent directory changed before commit",
                    False,
                )
            target_fd = os.open(
                parts[-1],
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent_fd,
            )
            payload = candidate.content.encode("utf-8")
            view = memoryview(payload)
            while view:
                written = os.write(target_fd, view)
                view = view[written:]
            os.fsync(target_fd)
            self.commit_count += 1
            return CommitResult("allow", "secure POSIX commit completed", True)
        except OSError as exc:
            reason = {
                errno.EEXIST: "target already exists or is a link",
                errno.ELOOP: "symlink encountered in the commit path",
                errno.ENOTDIR: "non-directory encountered in the commit path",
            }.get(exc.errno, f"secure POSIX commit rejected: {exc}")
            return CommitResult("block", reason, False)
        finally:
            if target_fd >= 0:
                os.close(target_fd)
            if parent_fd >= 0:
                os.close(parent_fd)

    def naive_commit(
        self,
        candidate: FileCandidate,
        snapshot: ParentSnapshot,
    ) -> CommitResult:
        target = self.host_path(candidate.virtual_path)
        try:
            with target.open("wb") as handle:
                handle.write(candidate.content.encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            self.commit_count += 1
            return CommitResult("allow", "naive absolute-path commit completed", True)
        except OSError as exc:
            return CommitResult("block", f"naive commit failed: {exc}", False)


class PosixPostStateObserver:
    """Observe committed file state without consulting a policy decision."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def host_path(self, virtual_path: str) -> Path:
        return self.workspace.joinpath(*_parts(virtual_path))

    @staticmethod
    def _parent_changed(target: Path, snapshot: ParentSnapshot) -> bool:
        try:
            info = os.stat(target.parent, follow_symlinks=True)
            return (
                int(info.st_dev) != snapshot.device
                or int(info.st_ino) != snapshot.inode
            )
        except OSError:
            return True

    def observe(
        self,
        candidate: FileCandidate,
        snapshot: ParentSnapshot,
    ) -> FileObservation:
        target = self.host_path(candidate.virtual_path)
        fd = -1
        try:
            fd = os.open(target, os.O_RDONLY)
            info = os.fstat(fd)
            data = os.pread(fd, int(info.st_size), 0)
            lexical = os.lstat(target)
            resolved = Path(os.path.realpath(target))
            parent_changed = self._parent_changed(target, snapshot)
            same_inode = (
                stat.S_ISREG(lexical.st_mode)
                and int(lexical.st_dev) == int(info.st_dev)
                and int(lexical.st_ino) == int(info.st_ino)
            )
            outside = not _is_below(resolved, Path(snapshot.resolved_parent))
            safe = (
                same_inode
                and int(lexical.st_nlink) == 1
                and _digest(data) == candidate.content_digest
                and not parent_changed
                and not outside
            )
            if safe:
                label = "safe"
                reason = "observed regular file matches candidate inode, bytes, and namespace"
            elif outside:
                label = "unsafe"
                reason = "committed pathname resolves outside the authorized notes namespace"
            elif int(lexical.st_nlink) > 1:
                label = "unsafe"
                reason = "committed inode has multiple hard links"
            elif parent_changed:
                label = "unsafe"
                reason = "committed parent directory differs from the authorized snapshot"
            elif not same_inode:
                label = "unsafe"
                reason = "observed pathname does not name the committed inode"
            else:
                label = "unsafe"
                reason = "observed bytes or file type differs from the candidate"
            return FileObservation(
                label,
                reason,
                candidate.virtual_path,
                str(resolved),
                _digest(data),
                int(lexical.st_nlink),
                parent_changed,
                outside,
            )
        except OSError as exc:
            return FileObservation(
                "review",
                f"post-state cannot be observed: {exc}",
                candidate.virtual_path,
                "",
                "",
                0,
                True,
                True,
            )
        finally:
            if fd >= 0:
                os.close(fd)
