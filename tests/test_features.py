import shutil

import numpy as np
import pandas as pd
import pytest

from src.audit_data import FILES, audit, load_inputs
from src.contracts import CLINICAL, ID, LAB, PRELAB, ROOT
from src.features_pipeline import DISCORDANCE, M3A_FEATURES, NATIVE_FEATURES, transform_record
from src.model_m3a import gower


def test_exact_legacy_reference_parity(tables):
    projected = [transform_record(row, None) for row in tables["raw"].to_dict("records")]
    for branch in ("m1", "m3a", "m3b"):
        expected = tables[branch]
        actual = pd.DataFrame([row[branch] for row in projected], index=expected.index)
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False, check_exact=True)
        # Whole-file regression against the published snapshot, independent of ID joins.
        legacy = pd.read_csv(ROOT / "mercurio_mvp_v4" / FILES[branch])
        pd.testing.assert_frame_equal(expected.reset_index(drop=True), legacy, check_exact=True)


def test_audit_reorders_by_id_and_rejects_duplicate(data_dir, tmp_path):
    for name in FILES.values():
        shutil.copyfile(data_dir / name, tmp_path / name)
    path = tmp_path / FILES["m1"]
    original = path.read_text().splitlines()
    path.write_text("\n".join([original[0], *reversed(original[1:])]) + "\n")
    _, _, report = audit(tmp_path)
    assert report["raw_matrix_parity"] and report["one_to_one"]
    assert report["lab_eligible_total"] == 1214
    rows = pd.read_csv(path, dtype={ID: str})
    rows.loc[1, ID] = rows.loc[0, ID]
    rows.to_csv(path, index=False)
    with pytest.raises(ValueError, match="ID explícito"):
        load_inputs(tmp_path)


def test_common_transform_preserves_zero_missing_and_prelab_isolation(artifacts):
    feature_artifacts = artifacts["transformers"]
    raw = {"fecha_notificacion": "2026-01-31", "fecha_exposicion": "2026-01-01",
           CLINICAL[0]: 0, CLINICAL[1]: 1, "exposicion_activa": 0, "sexo": "F"}
    before = transform_record(raw, feature_artifacts)
    after = transform_record(raw | dict.fromkeys(LAB, 50) | {"flag_anomalia_real": 1,
                             "indicador_laboratorio_pendiente": 1}, feature_artifacts)
    assert set(before["m1"]) == set(NATIVE_FEATURES)
    assert set(before["m3a"]) == set(M3A_FEATURES)
    assert "edad" not in before["m3a"] and "sexo" not in before["m3a"]
    for branch in ("m1", "m3a"):
        pd.testing.assert_series_equal(pd.Series(before[branch]), pd.Series(after[branch]))
        assert before[branch][CLINICAL[0]] == 0
        assert np.isnan(before[branch][CLINICAL[2]])
    assert before["m1"]["recencia_30d"] == .5
    assert before["m1"]["proporcion_sintomas_evaluados"] == 2 / 30
    assert before["m3b"] is None
    assert after["m3b"][LAB[0]] == np.log(50)


def test_gower_refuses_low_coverage(artifacts):
    row = transform_record({}, artifacts["transformers"])["m3a"]
    frame = pd.DataFrame([row])
    d, coverage = gower(frame, frame)
    assert np.isinf(d[0, 0])
    assert coverage[0, 0] < .5


def test_derived_bounds_and_discordance(artifacts):
    raw = {key: 0 for key in CLINICAL} | {
        "fecha_notificacion": "2026-02-01", "fecha_exposicion": "2026-01",
        "frecuencia_consumo_pescado_dias": 0, "EXT_32c_frecuencia_piscivoros_30d": 0,
        "via_respiratoria": 1, "tipo_ocupacional": 1, LAB[0]: 100,
    }
    prepared = transform_record(raw, artifacts["transformers"])
    a, b = prepared["m1"], prepared["m3b"]
    assert a["recencia_30d_min"] < a["recencia_30d_max"]
    assert np.isnan(a["recencia_30d"])
    assert a["I_min"] == a["I_max"] == 0
    assert set(DISCORDANCE) <= b.keys()
    assert b[DISCORDANCE[0]] == 100
    assert b[DISCORDANCE[2]] == 9
    assert b[DISCORDANCE[3]] == 1
