import subprocess


class GitBlobs:
    """Read immutable Git objects, independent of Windows checkout line endings."""

    def __init__(self, directory, revision):
        self.revision = revision
        self.process = subprocess.Popen(
            ["git", "-C", str(directory), "cat-file", "--batch"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def __enter__(self):
        return self

    def read(self, path):
        if "\n" in path or "\r" in path:
            raise ValueError("Invalid source path")
        self.process.stdin.write(f"{self.revision}:{path}\n".encode())
        self.process.stdin.flush()
        header = self.process.stdout.readline().decode().strip().split()
        if len(header) != 3 or header[1] != "blob":
            raise ValueError(f"Missing source blob at pinned revision: {path}")
        size = int(header[2])
        raw = self.process.stdout.read(size)
        if len(raw) != size or self.process.stdout.read(1) != b"\n":
            raise ValueError("Incomplete Git blob")
        return raw

    def __exit__(self, *args):
        self.process.stdin.close()
        self.process.wait(timeout=10)
        self.process.stdout.close()
        self.process.stderr.close()
