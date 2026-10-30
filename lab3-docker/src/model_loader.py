import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import joblib
import sklearn
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_URI = (Path(__file__).resolve().parent.parent / "model" / "1.0.0" / "model.pkl").as_uri()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IRIS_")
    artifact_uri: str = DEFAULT_URI
    artifact_version: str = "1.0.0"


class ModelLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedModel:
    model: object
    version: str
    metadata: dict


def _resolve_file(uri: str) -> Path:
    return Path(url2pathname(urlparse(uri).path))


def _resolve_gs(uri: str) -> Path:
    raise NotImplementedError("gs:// backend not implemented yet")


RESOLVERS = {"file": _resolve_file, "gs": _resolve_gs}


def _sha256(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def load_model(settings: Settings) -> LoadedModel:
    scheme = urlparse(settings.artifact_uri).scheme
    if scheme not in RESOLVERS:
        raise ModelLoadError(f"unsupported URI scheme: {scheme!r}")
    model_path = RESOLVERS[scheme](settings.artifact_uri)
    meta_path = model_path.with_name("metadata.json")

    if not model_path.is_file() or not meta_path.is_file():
        raise ModelLoadError(f"missing model or metadata at {model_path.parent}")
    meta = json.loads(meta_path.read_text())

    if meta["version"] != settings.artifact_version:
        raise ModelLoadError(f"version mismatch: config {settings.artifact_version}, artifact {meta['version']}")
    if meta["sklearn_version"] != sklearn.__version__:
        raise ModelLoadError(f"sklearn mismatch: trained {meta['sklearn_version']}, running {sklearn.__version__}")
    if _sha256(model_path) != meta["sha256"]:
        raise ModelLoadError("sha256 mismatch: model file differs from metadata")

    return LoadedModel(model=joblib.load(model_path), version=meta["version"], metadata=meta)
