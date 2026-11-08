"""Process coordination between generation and retained evidence access."""
from contextlib import contextmanager
from functools import wraps
import os
from pathlib import Path
import tempfile

from .manifest import PlanError


@contextmanager
def evidence_access():
    # One per-user OS lock; kernel releases it after crashes. No stale lock deletion.
    path = Path(tempfile.gettempdir()) / 'legacy-diff-evidence-access.lock'
    with path.open('a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise PlanError('Generation or evidence access is active; retry after it finishes.', 'unsupported') from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def coordinated(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with evidence_access():
            return function(*args, **kwargs)
    return wrapped
