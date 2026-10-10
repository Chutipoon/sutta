"""Bounded, checksum-verified HTTP ranges for large model files on unreliable links."""
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx


def ranged_download(url, destination, size, sha256, step=32*1024*1024):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        with destination.open("rb") as file:
            if hashlib.file_digest(file, "sha256").hexdigest() == sha256:
                return
        raise ValueError("Existing model file checksum mismatch; preserve it and choose another model directory")
    part = destination.with_suffix(destination.suffix + ".range.partial")
    state_file = destination.with_suffix(destination.suffix + ".range.json")
    state = {"size": size, "sha256": sha256, "step": step, "complete": []}
    if part.exists() and state_file.exists():
        previous = json.loads(state_file.read_text(encoding="utf-8"))
        if any(previous[k] != state[k] for k in ("size", "sha256", "step")):
            raise ValueError("Partial model belongs to another revision")
        state = previous
    else:
        with part.open("wb") as file:
            file.truncate(size)
    complete = set(state["complete"])
    total = (size+step-1)//step

    def request(i):
        start, end = i*step, min(size, (i+1)*step)-1
        for attempt in range(3):
            try:
                # Separate resolver cache entries for independently signed byte ranges.
                with (
                    httpx.Client(follow_redirects=True, timeout=60) as client,
                    client.stream("GET", url+f"?range_part={i}", headers={"Range": f"bytes={start}-{end}"}) as response,
                ):
                    if response.status_code != 206 or response.headers.get("content-range") != f"bytes {start}-{end}/{size}":
                        raise ValueError("Model host did not honor exact byte range")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > end-start+1:
                            raise ValueError("Model range exceeded expected size")
                    if len(body) != end-start+1:
                        raise ValueError("Incomplete model range")
                    return i, start, body
            except httpx.HTTPError:
                if attempt == 2:
                    raise RuntimeError("Model range download failed after three attempts; rerun to resume") from None

    with part.open("r+b") as file, ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(request, i) for i in range(total) if i not in complete}
        for future in as_completed(futures):
            i, start, body = future.result()
            file.seek(start)
            file.write(body)
            file.flush()
            complete.add(i)
            state["complete"] = sorted(complete)
            state_temp = state_file.with_suffix(".tmp")
            state_temp.write_text(json.dumps(state), encoding="utf-8")
            os.replace(state_temp, state_file)
            print(f"Model ranges {len(complete)}/{total}", flush=True)
            futures.remove(future)
    with part.open("rb") as file:
        if hashlib.file_digest(file, "sha256").hexdigest() != sha256:
            raise ValueError("Downloaded model checksum mismatch; model was not activated")
    os.replace(part, destination)
    state_file.unlink()
