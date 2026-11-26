import pytest

from src.audit_data import load_inputs, prepare_default_data
from src.contracts import ROOT
from src.inference import load_artifacts
from src.train_models import train


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory):
    prepared = ROOT / "data"
    if not prepared.exists():
        prepared = tmp_path_factory.mktemp("data")
        prepare_default_data(prepared)
    return prepared


@pytest.fixture(scope="session")
def tables(data_dir):
    result, _ = load_inputs(data_dir)
    return result


@pytest.fixture(scope="session")
def artifacts(data_dir, tmp_path_factory):
    models = ROOT / "models"
    if not (models / "manifest.json").exists():
        temp = tmp_path_factory.mktemp("training")
        models = temp / "models"
        train(data_dir, models, temp / "reports")
    return load_artifacts(models)
