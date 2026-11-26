import json

from src.contracts import LAB
from src.model_m1 import MODEL_TARGETS, PAIRS
from src.inference import predict_patient


def test_inference_all_branches_and_shap(tables, artifacts):
    selected = tables["raw"].loc[tables["raw"][LAB].notna().any(axis=1)].iloc[0].to_dict()
    result = predict_patient(selected, artifacts)
    assert set(result["m1"]) == set(MODEL_TARGETS)
    for risk in result["m1"].values():
        assert 0 <= risk["probabilidad"] <= 1
        assert len(risk["factores_modelo_independiente"]) == 6
        assert risk["alerta_triaje"] == (risk["probabilidad"] >= risk["umbral"])
    for lower, higher in PAIRS:
        assert result["m1"][higher]["probabilidad"] <= result["m1"][lower]["probabilidad"]
        assert not result["m1"][higher]["alerta_triaje"] or result["m1"][lower]["alerta_triaje"]
    assert result["m3a"]["id"] >= -1
    assert result["m3b"]["elegible"]
    assert isinstance(result["m3b"]["alerta_revision"], bool)
    assert "experimentales" in result["aviso_experimental"]
    json.dumps(result, allow_nan=False)


def test_inference_without_valid_laboratory(artifacts):
    for record in ({}, {"tipo_muestra": "Sangre", "EXT_67b_concentracion_hg_resultado": 20,
                         "EXT_67c_unidad_medida": "ug/g"}):
        result = predict_patient(record, artifacts)
        assert result["m3b"] == {"elegible": False, "alerta_revision": None, "puntaje": None}
        assert result["m3a"]["id"] == -1
        assert result["normativo"]["caso"]["clasificacion"] != "Confirmado"
