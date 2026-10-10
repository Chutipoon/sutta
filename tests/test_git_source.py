import subprocess

from sutta.git_source import GitBlobs


def test_git_blobs_ignore_checkout_line_endings(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    raw = b'{\n  "test:1": "original ",\n  "test:2": "next "\n}\n'
    file = tmp_path/"source.json"
    file.write_bytes(raw)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "core.autocrlf=false", "add", "source.json"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Fixture", "-c",
                    "user.email=fixture@example.invalid", "commit", "-m", "fixture"], check=True, capture_output=True)
    revision = subprocess.check_output(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True).strip()
    file.write_bytes(raw.replace(b"\n", b"\r\n"))
    assert file.read_bytes() != raw
    with GitBlobs(tmp_path, revision) as reader:
        assert reader.read("source.json") == raw
        assert reader.read("source.json") == raw  # Multiple requests in one batch process.
