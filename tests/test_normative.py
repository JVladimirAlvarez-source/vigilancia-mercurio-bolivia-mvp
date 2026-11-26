import pytest

from src.normative_engine import (assess_vulnerability, calculate_edi, classify_case,
                                  recommend_biomarker, validate_record)


def test_states_and_traceability():
    assert classify_case({})["clasificacion"] == "No cumple criterios / info insuficiente"
    record = {"procedencia_zona_riesgo_hg": True}
    assert classify_case(record)["clasificacion"] == "Sospechoso"
    record.update(manifestacion_clinica_compatible=True, lab_hg_orina_ug_g=55,
                  lab_hg_sangre_ug_l=21, laboratorio_sangre_validado=True)
    assert classify_case(record)["clasificacion"] == "Probable"
    record["laboratorio_orina_validado"] = True
    result = classify_case(record)
    assert result["clasificacion"] == "Confirmado"
    assert "§15.2 p. 36" in result["referencia"] and "Cuadros 2–3 p. 32" in result["referencia"]
    for partial in ({"lab_hg_orina_ug_g": 50}, {"lab_hg_sangre_ug_l": 20},
                    {"lab_hg_orina_ug_g": None, "lab_hg_orina_ug_g_cr": 60},
                    {"lab_hg_sangre_ug_l": None, "lab_hg_cordon_ug_l": 30},
                    {"lab_hg_orina_ug_g_unidad": "ug/g Cr"}):
        assert classify_case(record | partial)["clasificacion"] == "Probable"


def test_wrong_unit_and_chronology():
    result = validate_record({
        "tipo_muestra": "Cabello", "EXT_67b_concentracion_hg_resultado": 3,
        "EXT_67c_unidad_medida": "ug/L", "fecha_envio_lab": "2026-01-01",
        "fecha_toma_muestra": "2026-01-02", "clin_35_nauseas": .5, "edad": -1,
    })
    assert not result["valido"]
    assert set(result["errores"]) == {
        "fecha_envio_lab", "EXT_67c_unidad_medida", "clin_35_nauseas", "edad"}


def test_edi_measured_and_reference():
    record = {"EXT_10b_peso_corporal_kg": 60, "frecuencia_consumo_pescado_dias": 10,
              "EXT_32d_tamano_porcion_gramos": 180, "EXT_32c_frecuencia_piscivoros_30d": 10}
    assert calculate_edi(record)["edi"] == pytest.approx(1.71)
    assert calculate_edi(record)["referencial"]
    assert calculate_edi(record | {"concentracion_mehg_pescado_ug_g": .4})["edi"] == .4
    assert calculate_edi({"frecuencia_consumo_pescado_dias": 0,
                          "EXT_10b_peso_corporal_kg": 60})["edi"] == 0


def test_priority_flags_remain_independent_and_mixed_route():
    assert assess_vulnerability({"sexo": "F", "edad": 16, "embarazo_actual": 1}) == {
        "embarazo": True, "lactancia": None, "mujer_edad_fertil": True, "menor_18": True,
        "exposicion_fetal": True, "exposicion_cronica_sistematica": None}
    assert recommend_biomarker({"tipo_exposicion": "tipo_ocupacional", "consumo_pescado_rio": 1,
                                "frecuencia_consumo_pescado_dias": 5})["matrices"] == ["Orina", "Cabello"]
