"""Verificación del contrato entre Streamlit y los artefactos congelados."""
import ast
import hashlib
import shutil

import pytest
from streamlit.testing.v1 import AppTest

from app import app

APP_FILE = app.ROOT / "app" / "app.py"


def test_import_has_no_training_or_ui_execution(monkeypatch):
    # Running the source under an imported name must not enter the UI or load resources.
    import runpy

    def unexpected(*args, **kwargs):
        pytest.fail("Importar la aplicación ejecutó un recurso o inicializó la página")

    monkeypatch.setattr(app.st, "set_page_config", unexpected)
    monkeypatch.setattr("src.inference.load_artifacts", unexpected)
    imported = runpy.run_path(str(APP_FILE), run_name="app_import_test")
    assert callable(imported["main"])
    tree = ast.parse(APP_FILE.read_text(encoding="utf-8"))
    modules = [node.name for node in ast.walk(tree) if isinstance(node, ast.alias)]
    modules += [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert all("train_models" not in name and "model_m" not in name for name in modules)
    assert all(not isinstance(node, ast.Attribute) or node.attr not in {"fit", "fit_transform", "train"}
               for node in ast.walk(tree))


def test_cache_checks_integrity_and_rejects_modified_artifact(tmp_path, monkeypatch):
    artifacts, manifest, digest = app.load_engine()
    assert app.load_engine()[0] is artifacts
    assert manifest["contract_version"] == 2
    assert digest == hashlib.sha256((app.MODELS / "manifest.json").read_bytes()).hexdigest()
    path = tmp_path / "models"
    shutil.copytree(app.MODELS, path)
    with (path / "m1" / "thresholds.json").open("ab") as file:
        file.write(b" ")
    with monkeypatch.context() as scoped:
        scoped.setattr(app, "MODELS", path)
        app.load_engine.clear()
        try:
            with pytest.raises(ValueError, match="Artefacto incongruente"):
                app.load_engine()
        finally:
            app.load_engine.clear()


def click(screen, label):
    next(button for button in screen.button if button.label == label).click().run(timeout=45)
    assert not screen.exception
    return screen


def manual_screen(compatible=None):
    screen = AppTest.from_file(str(APP_FILE)).run(timeout=45)
    assert not screen.exception
    screen.radio(key="input_mode").set_value(app.MANUAL).run(timeout=45)
    screen.selectbox(key="triage:manual:antecedente_exposicion_hg").set_value(1)
    if compatible is not None:
        screen.selectbox(key="triage:manual:manifestacion_clinica_compatible").set_value(compatible)
    return click(screen, "Evaluar ficha")


@pytest.mark.parametrize(("compatible", "expected"), [(None, "Sospechoso"), (1, "Probable")])
def test_triage_normative_states(compatible, expected):
    screen = manual_screen(compatible)
    assert len(screen.tabs) == 3
    result = screen.session_state["triage_result"]["result"]
    assert result["normativo"]["caso"]["clasificacion"] == expected
    assert any(message.value == app.EXPERIMENTAL for message in screen.info)
    assert any(message.value == app.SYNTHETIC for message in screen.warning)
    assert any(element.value == "Integridad SHA-256 verificada" for element in screen.success)


def test_manual_confirmation_requires_validated_dosages_in_correct_units():
    screen = manual_screen(1)
    prefix = "lab:active:triage:manual"
    blood = "lab_hg_sangre_ug_l"
    urine = "lab_hg_orina_ug_g"
    for key, value in ((blood, 30.), (urine, 65.)):
        screen.number_input(key=f"{prefix}:{key}:value").set_value(value)
        screen.checkbox(key=f"{prefix}:{key}:validated").check()
    screen.selectbox(key=f"{prefix}:{urine}:unit").set_value("µg/g creatinina")
    click(screen, "Evaluar laboratorio")
    invalid = screen.session_state["lab_result"]["result"]["normativo"]
    assert invalid["caso"]["clasificacion"] == "Probable"
    assert urine in invalid["validacion"]["errores"]
    screen.selectbox(key=f"{prefix}:{urine}:unit").set_value("µg/g")
    click(screen, "Evaluar laboratorio")
    assert screen.session_state["lab_result"]["result"]["normativo"]["caso"]["clasificacion"] == "Confirmado"


def test_patient_without_laboratory_omits_m3b():
    screen = manual_screen(1)
    click(screen, "Evaluar laboratorio")
    saved = screen.session_state["lab_result"]
    assert set(saved["record"]).isdisjoint(app.LAB)
    assert saved["result"]["m3b"] == {"elegible": False, "alerta_revision": None, "puntaje": None}


def demo_app(directory):
    from pathlib import Path

    from app.app import main

    main(Path(directory))


def test_demonstration_discordance_uses_test_row_and_displays_alert(data_dir):
    screen = AppTest.from_function(demo_app, args=(str(data_dir),)).run(timeout=45)
    selector = screen.selectbox(key="demo_case")
    assert len(selector.options) == 4
    example = "Perfil asintomático con discordancia preanalítica"
    selector.set_value(example).run(timeout=45)
    click(screen, "Evaluar ficha")
    demo = screen.session_state["triage_result"]["demo"]
    assert app.load_dashboard_data(data_dir).loc[demo, "split"] == "test"
    click(screen, "Evaluar laboratorio")
    result = screen.session_state["lab_result"]["result"]
    assert result["m3b"]["alerta_revision"] is True
    assert any(message.value == app.ALERT for message in screen.warning)
    assert result["normativo"]["caso"]["clasificacion"] != "Confirmado"
