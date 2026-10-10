import os
from pathlib import Path

REVISION = "83589dcd2b23ed6b5fcb02361d958f5b8a9ef057"
SOURCE = "https://github.com/suttacentral/bilara-data"
PRIORITY = ("sujato", "brahmali", "kelly", "soma", "suddhaso", "kovilo")
MODEL = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"


def data_dir():
    return Path(os.environ.get("SUTTA_DATA", "data")).resolve()


def db_path():
    return data_dir() / "corpus.sqlite"


def index_path():
    return data_dir() / "index.sqlite"


def model_dir():
    return Path(os.environ.get("SUTTA_MODEL_DIR", "models/e5-small")).resolve()
