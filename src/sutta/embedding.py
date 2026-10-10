import json
import os
from functools import lru_cache

import numpy as np
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

from .config import MODEL, MODEL_REVISION, model_dir


def directory_for(profile):
    from pathlib import Path
    return model_dir() if profile == "e5" else Path(os.environ.get("SUTTA_BGE_DIR", "models/bge-m3")).resolve()


def download(profile="e5"):
    directory = directory_for(profile)
    directory.mkdir(parents=True, exist_ok=True)
    revision = MODEL_REVISION if profile == "e5" else "5617a9f61b028005a4858fdac845db406aefb181"
    name = MODEL if profile == "e5" else "BAAI/bge-m3"
    files = ["onnx/model.onnx", "tokenizer.json", "config.json"]
    if profile == "bge":
        files += ["onnx/model.onnx_data", "onnx/Constant_7_attr__value"]
    for file in files:
        if file == "onnx/model.onnx_data" and os.environ.get("SUTTA_RANGE_DOWNLOAD") == "1":
            from .model_download import ranged_download
            ranged_download(f"https://huggingface.co/{name}/resolve/{revision}/{file}", directory/file,
                            2266820608, "1eebfb28493f67bba03ce0ef64bfdc7fc5a3bd9d7493f818bb1d78cd798416b4")
        else:
            hf_hub_download(name, file, revision=revision, local_dir=directory)
    (directory / "manifest.json").write_text(json.dumps({"model": name, "revision": revision}), encoding="utf-8")
    return {"model": name, "revision": revision, "directory": str(directory)}


class Encoder:
    def __init__(self, profile="e5"):
        import onnxruntime as ort
        self.profile = profile
        self.dimension = 384 if profile == "e5" else 1024
        directory = directory_for(profile)
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_padding()
        self.tokenizer.enable_truncation(max_length=512)
        options = ort.SessionOptions()
        options.intra_op_num_threads = int(os.environ.get("SUTTA_THREADS", "4"))
        self.session = ort.InferenceSession(str(directory / "onnx/model.onnx"), options,
                                           providers=["CPUExecutionProvider"])
        self.inputs = {x.name for x in self.session.get_inputs()}
        self.fingerprint = (directory / "manifest.json").read_text(encoding="utf-8")

    def count(self, text):
        return len(self.tokenizer.encode(("passage: " if self.profile == "e5" else "") + text).ids)

    def encode(self, texts, query=False):
        prefix = ("query: " if query else "passage: ") if self.profile == "e5" else ""
        encoded = self.tokenizer.encode_batch([prefix + x for x in texts])
        inputs = {"input_ids": np.array([x.ids for x in encoded], dtype=np.int64),
                  "attention_mask": np.array([x.attention_mask for x in encoded], dtype=np.int64),
                  "token_type_ids": np.array([x.type_ids for x in encoded], dtype=np.int64)}
        outputs = self.session.run(None, {k: v for k, v in inputs.items() if k in self.inputs})
        hidden = outputs[0]
        if hidden.ndim != 3 or hidden.shape[-1] != self.dimension:
            raise ValueError(f"Unexpected hidden-state shape: {hidden.shape}")
        mask = inputs["attention_mask"][..., None]
        pooled = (hidden * mask).sum(axis=1) / mask.sum(axis=1) if self.profile == "e5" else hidden[:, 0]
        pooled = pooled / np.linalg.norm(pooled, axis=1, keepdims=True).clip(1e-12)
        return pooled.astype(np.float32)


@lru_cache(maxsize=2)
def encoder(profile="e5"):
    return Encoder(profile)
