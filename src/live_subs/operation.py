"""One operation per data directory across desktop and terminal entry points."""

import fcntl
import os


def acquire_operation(directory, inherited_fd=None):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "desktop-operation.lock"
    if inherited_fd is None:
        lock = path.open("a")
    else:
        descriptor = int(inherited_fd)
        actual, expected = os.fstat(descriptor), path.stat()
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            raise RuntimeError("Inherited operation lock does not match the data directory")
        lock = os.fdopen(os.dup(descriptor), "a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock.close()
        raise RuntimeError(
            "Another TingSub window or terminal is already working in this directory"
        ) from exc
    # Never LOCK_UN: the desktop and child share the same open file description.
    return lock
