"""Fetch ML model artifacts from Hugging Face Hub.

The model files (downscaler.pkl, forecaster.pt) are NOT committed to git -- the
full-data downscaler RF is ~670 MB, past GitHub's limit -- so they are hosted on
the Hub instead (.gitignored locally). Set HF_REPO_ID and they are downloaded at
startup. With HF_REPO_ID unset this is a no-op and the app uses whatever model
files are already on disk (e.g. a local training run); a fresh deploy must set
HF_REPO_ID or the artifacts will be missing.

Environment
-----------
HF_REPO_ID   e.g. "your-username/aquasignal-models" (unset = use repo files)
HF_TOKEN     access token, only needed for private repos
MODELS_DIR   download target, default /tmp/models

When HF_REPO_ID is set, also point the API at the downloaded copies:
    AQUASIGNAL_DOWNSCALER_PATH=/tmp/models/downscaler.pkl
    AQUASIGNAL_FORECASTER_PATH=/tmp/models/forecaster.pt

Runs standalone (``python -m models.download``) from start.sh before the API
boots, and again as a guard inside the FastAPI lifespan (idempotent: files
already on disk are never re-downloaded).
"""

import logging
import os
from pathlib import Path

LOG = logging.getLogger("aquasignal.models.download")

MODEL_FILES = ("downscaler.pkl", "forecaster.pt")


def ensure_models() -> None:
    """Download model files from HF Hub unless they already exist locally."""
    repo_id = os.environ.get("HF_REPO_ID")
    if not repo_id:
        LOG.info("HF_REPO_ID not set -- using model files already on disk, if any")
        return

    # Imported lazily so the API never needs huggingface_hub unless HF is used.
    from huggingface_hub import hf_hub_download

    models_dir = Path(os.environ.get("MODELS_DIR", "/tmp/models"))
    models_dir.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HF_TOKEN") or None

    for filename in MODEL_FILES:
        target = models_dir / filename
        if target.exists() and target.stat().st_size > 0:
            LOG.info("%s already present (%d bytes) -- skipping", target, target.stat().st_size)
            continue
        LOG.info("Downloading %s from %s ...", filename, repo_id)
        downloaded = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            token=token,
            local_dir=models_dir,
        )
        LOG.info("Fetched %s -> %s", filename, downloaded)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ensure_models()
