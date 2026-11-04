import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("TRAFFIC_AI_SECRET", "test-secret-key")  # tests never write data/.secret_key

from backend import model as ml  # noqa: E402
from backend import preprocessing as pp  # noqa: E402


@pytest.fixture(scope="session")
def pipeline(tmp_path_factory):
    """The real Pune CSV run through the pipeline once (outputs go to a temp folder, never to data/processed)."""
    return pp.run_preprocessing(out_dir=tmp_path_factory.mktemp("processed"))


@pytest.fixture(scope="session")
def trained(pipeline, tmp_path_factory):
    """Models trained on the real data into a temp folder."""
    folder = tmp_path_factory.mktemp("models")
    ml.MODEL_PATH, ml.REPORT_PATH = folder / "m.joblib", folder / "r.json"
    report = ml.train_and_save(pipeline["arrivals"])
    return ml.load_model()[0], report
