"""Presentación Streamlit del contrato v2 del backend congelado."""
import hashlib
import json
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.contracts import CLINICAL, ID, LAB, SCHEMA
from src.derived_features import DOMAINS
from src.features_pipeline import DISCORDANCE, project_record, transform_record
from src.inference import load_artifacts, predict_patient
from src.normative_engine import RESULT, UNIT, assess_vulnerability, classify_case, day

MODELS = ROOT / "models"
REPORTS = ROOT / "reports"
DATA = ROOT / "data"
MANUAL = "Nueva ficha epidemiológica manual"
DEMO = "Caso de demostración del conjunto test"
ACTIVE_LAB = "Ficha activa de triaje"
TEST_LAB = "Registro test con laboratorio"
EXPERIMENTAL = "Estimación experimental del simulador (no diagnóstica)"
ALERT = "Alerta de revisión preanalítica (discordancia clínico-toxicológica)"
SYNTHETIC = "Cohorte sintética · N = 1.500 · semilla = 42. No estima prevalencias epidemiológicas reales de Bolivia."
TARGET_LABELS = {
    "y_mehg_cabello_epa": "Cabello EPA ≥1 µg/g",
    "y_mehg_cabello_bolivia": "Cabello Bolivia ≥3 µg/g",
    "y_mehg_cabello_5": "Cabello >5 µg/g",
    "y_hg_urinario_hbm2": "Orina HBM-II ≥20 µg/g Cr",
    "y_hg_urinario_guia537": "Orina Guía 537 ≥50 µg/g Cr",
}
UNITS = {"µg/g": "ug/g", "µg/g creatinina": "ug/g Cr", "µg/L": "ug/L"}
LAB_FIELDS = {
    "Cabello": (LAB[0], "µg/g"),
    "Orina · masa de muestra": ("lab_hg_orina_ug_g", "µg/g"),
    "Orina · creatinina": (LAB[1], "µg/g creatinina"),
    "Sangre": (LAB[2], "µg/L"),
}
PRIORITY = {
    "embarazo": "Embarazo", "lactancia": "Lactancia", "mujer_edad_fertil": "Edad fértil (15–49 años)",
    "menor_18": "Menor de 18 años", "exposicion_fetal": "Prioridad fetal",
    "exposicion_cronica_sistematica": "Exposición crónica sistemática",
}
PALETTE = ["#087f75", "#5978bc", "#be6e3c", "#677e85", "#8e69a4"]
HEADER = """
<style>
.block-container {max-width: 1250px; padding-top: 2.5rem; padding-bottom: 4rem;}
.mercurio-header {background: #103b3b; color: #fff; padding: 2.1rem 2.4rem;
                  border-radius: 16px; border-left: 6px solid #57c9a9; margin-bottom: 1rem;}
.mercurio-header h1 {color: #fff; font-size: clamp(1.65rem, 3.2vw, 2.65rem);
                      line-height: 1.12; margin: 0 0 .8rem; padding: 0;}
.mercurio-header p {color: #d2f0e8; margin: 0; max-width: 70ch;}
[data-testid="stMetric"] {border: 1px solid #10847640; border-radius: 10px; padding: .65rem .9rem;}
</style>
<header class="mercurio-header">
<h1>Vigilancia Inteligente de Intoxicación por Mercurio — Bolivia (MVP)</h1>
<p>Alineado con Guía Técnica N.º 537 (Min. Salud y Deportes, 2024)</p>
</header>
"""


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_resource(show_spinner="Verificando artefactos del backend…")
def load_engine():
    """Valida primero el contrato y los hashes usando el cargador congelado."""
    artifacts = load_artifacts(MODELS)
    manifest_path = MODELS / "manifest.json"
    return artifacts, read_json(manifest_path), hashlib.sha256(manifest_path.read_bytes()).hexdigest()


@st.cache_data(show_spinner=False)
def load_dashboard_data(data_dir=DATA):
    """Lee la ficha sintética verificada y cruza únicamente ID y split."""
    paths = [data_dir / "ficha_mercurio_bolivia_v2.csv",
             data_dir / "auditoria_latente_NO_ENTRENAR.csv"]
    hashes = read_json(MODELS / "manifest.json")["data_sha256"]
    for path in paths:
        if hashlib.sha256(path.read_bytes()).hexdigest() != hashes[path.name]:
            raise ValueError(f"La huella de {path.name} difiere de la cohorte congelada.")
    raw = pd.read_csv(paths[0], dtype={ID: "string"},
                      usecols=lambda key: key in FICHA_FIELDS or key in STORED_LAB or key in {ID, "departamento"})
    split = pd.read_csv(paths[1], usecols=[ID, "split"], dtype={ID: "string"})
    joined = raw.merge(split, on=ID, validate="one_to_one")
    if (len(joined) != len(raw) or len(joined) != len(split)
            or joined["split"].value_counts().to_dict() != SCHEMA["partitions"]):
        raise ValueError("La ficha y el archivo de particiones no coinciden por ID.")
    return joined.set_index(ID)


LABELS = {
    "edad": "Edad (años)", "sexo": "Sexo registrado", "EXT_10b_peso_corporal_kg": "Peso (kg)",
    "embarazo_actual": "Embarazo", "lactancia_actual": "Lactancia", "numero_hijos": "Número de hijos",
    "antecedente_aborto_espontaneo": "Antecedente de aborto espontáneo",
    "antecedente_exposicion_hg": "Exposición confirmada a mercurio",
    "procedencia_zona_riesgo_hg": "Procedencia de zona de riesgo",
    "manifestacion_clinica_compatible": "Manifestación compatible según evaluación profesional",
    "EXT_27b_quema_amalgama_frecuencia": "Frecuencia de quema de amalgama",
    "EXT_27c_quema_espacio_cerrado_o_vivienda": "Quema en recinto cerrado o vivienda",
    "EXT_27d_uso_retorta": "Uso de retorta", "EXT_32b_especies_piscivoras_alto_hg": "Consumo de especies piscívoras",
    "EXT_32c_frecuencia_piscivoros_30d": "Consumo de piscívoros (días/30)",
    "EXT_32d_tamano_porcion_gramos": "Porción de pescado (g)",
    "frecuencia_consumo_pescado_dias": "Consumo de pescado (días/30)",
    "ingesta_pescado_g_dia": "Ingesta directa de pescado (g/día)",
    "concentracion_mehg_pescado_ug_g": "Metilmercurio medido en pescado (µg/g)",
    "EXT_64b_fecha_inicio_sintomas": "Inicio de síntomas (AAAA-MM-DD)",
    "fecha_exposicion": "Última exposición (AAAA-MM-DD o AAAA-MM)",
    "fecha_notificacion": "Notificación (AAAA-MM-DD)",
    "fecha_inicio_exposicion": "Inicio de exposición (AAAA-MM-DD)",
    "fecha_cese_exposicion": "Cese de exposición (AAAA-MM-DD o AAAA-MM)",
    "clin_eretismo": "Eretismo documentado", "clin_memoria": "Alteración de memoria",
    "clin_concentracion": "Alteración de concentración",
}
DEMOGRAPHICS = ("edad", "sexo", "EXT_10b_peso_corporal_kg", "embarazo_actual", "lactancia_actual",
                "numero_hijos", "antecedente_aborto_espontaneo")
EXPOSURE_FIELDS = ("antecedente_exposicion_hg", "procedencia_zona_riesgo_hg", "ocupacion",
                   "lugar_probable_exposicion", "ocupacion_momento_exposicion", "tipo_parentesco",
                   "antecedente_familiar_mineria", "presencia_empresas_mineras",
                   "antecedente_exposicion_anterior_anos", "tiempo_exposicion_horas_equiv",
                   "horas_quema_amalgama", "EXT_27b_quema_amalgama_frecuencia",
                   "EXT_27c_quema_espacio_cerrado_o_vivienda", "EXT_27d_uso_retorta",
                   "via_respiratoria", "via_dermica", "via_oral", "via_desconocida",
                   "tipo_ocupacional", "tipo_accidental", "tipo_ambiental", "exposicion_cronica_sistematica")
DIET_TIME = ("consumo_pescado_rio", "frecuencia_consumo_pescado_dias", "EXT_32b_especies_piscivoras_alto_hg",
             "EXT_32c_frecuencia_piscivoros_30d", "EXT_32d_tamano_porcion_gramos", "ingesta_pescado_g_dia",
             "concentracion_mehg_pescado_ug_g", "exposicion_dietetica_cronica", "fecha_notificacion",
             "fecha_exposicion", "fecha_inicio_exposicion", "fecha_cese_exposicion",
             "exposicion_activa", "EXT_64b_fecha_inicio_sintomas")
CLINICAL_FIELDS = ("manifestacion_clinica_compatible", "clin_eretismo", "clin_38_gingivitis",
                   "clin_62_temblor_distal", "clin_memoria", "clin_concentracion")
FICHA_FIELDS = {*DEMOGRAPHICS, *EXPOSURE_FIELDS, *DIET_TIME, *CLINICAL_FIELDS, *CLINICAL,
                "via_exposicion", "tipo_exposicion"}
STORED_LAB = {*LAB, "fecha_toma_muestra", "fecha_envio_lab", "EXT_67d_longitud_segmento_cabello_cm"}
BINARY = set(SCHEMA["binary"]) | {"procedencia_zona_riesgo_hg", "manifestacion_clinica_compatible",
                                  "clin_eretismo", "clin_memoria", "clin_concentracion",
                                  "exposicion_activa", "exposicion_cronica_sistematica",
                                  "exposicion_dietetica_cronica"}
NUMERIC = set(SCHEMA["ranges"]) | {
    "numero_hijos", "antecedente_exposicion_anterior_anos", "tiempo_exposicion_horas_equiv",
    "horas_quema_amalgama", "EXT_27b_quema_amalgama_frecuencia", "ingesta_pescado_g_dia",
    "concentracion_mehg_pescado_ug_g",
}


def label(key):
    return LABELS.get(key, key.removeprefix("EXT_").removeprefix("clin_").split("_", 1)[-1].replace("_", " ").capitalize()
                      if key.startswith(("EXT_", "clin_")) else key.replace("_", " ").capitalize())


def source_record(row):
    """Desidentifica y convierte las categorías agrupadas al contrato editable."""
    raw = {key: value for key, value in row.items() if key in FICHA_FIELDS and pd.notna(value)}
    projected = project_record(raw)["m1"]
    fields = (FICHA_FIELDS - {"via_exposicion", "tipo_exposicion"})
    return {key: raw.get(key, projected.get(key)) for key in fields
            if pd.notna(raw.get(key, projected.get(key)))}


@st.cache_data(show_spinner=False)
def pick_examples(cohort, _artifacts, manifest_digest):
    """Selecciona perfiles con datos declarados y el score congelado, sin etiquetas latentes."""
    test = cohort.loc[cohort["split"].eq("test")].sort_index()
    respiratory = test["via_exposicion"].fillna("").str.contains("via_respiratoria")
    occupational = test["tipo_exposicion"].fillna("").str.contains("tipo_ocupacional")
    fish = test["EXT_32c_frecuencia_piscivoros_30d"].gt(0)
    maternal = test["embarazo_actual"].eq(1) | test["lactancia_actual"].eq(1)
    prototype_conditions = {
        "Exposición ocupacional a vapor de Hg⁰": respiratory & occupational & ~fish,
        "Consumo de peces piscívoros en la cuenca amazónica": fish & test["departamento"].eq("Beni") & test["lugar_probable_exposicion"].eq("Alimentacion"),
        "Vulnerabilidad materno-infantil": maternal,
    }
    examples = {name: str(test.index[mask][0]) for name, mask in prototype_conditions.items() if mask.any()}
    candidates = test.loc[test[list(LAB)].notna().any(axis=1) & test[CLINICAL].eq(1).sum(axis=1).eq(0)
                          & test[CLINICAL].notna().mean(axis=1).ge(.70)]
    model = _artifacts["m3b"]["model"]
    if not candidates.empty:
        vectors = [transform_record(row, _artifacts["transformers"])["m3b"]
                   for row in candidates.to_dict("records")]
        frame = pd.DataFrame(vectors, index=candidates.index, columns=model.feature_names_in_)
        scores = pd.Series(-model.score_samples(frame), index=candidates.index)
        candidate = scores.idxmax()
        if scores[candidate] >= _artifacts["m3b"]["threshold"]:
            examples["Perfil asintomático con discordancia preanalítica"] = str(candidate)
    return examples


def widget(key, initial, prefix):
    value = initial.get(key)
    if key in BINARY:
        options = (None, 0, 1, "no aplica") if key in CLINICAL else (None, 0, 1)
        labels = {None: "Sin dato", 0: "No", 1: "Sí", "no aplica": "No aplica"}
        selected = options.index(value) if value in options else 0
        result = st.selectbox(label(key), options, index=selected, format_func=labels.__getitem__,
                              key=f"{prefix}:{key}")
        return bool(result) if key == "exposicion_dietetica_cronica" and result is not None else result
    if key == "sexo":
        options = (None, "F", "M")
        labels = {None: "Sin dato", "F": "Femenino", "M": "Masculino"}
        return st.selectbox(label(key), options, index=options.index(value) if value in options else 0,
                            format_func=labels.__getitem__, key=f"{prefix}:{key}")
    if key in NUMERIC:
        bounds = SCHEMA["ranges"].get(key)
        return st.number_input(label(key), min_value=float(bounds[0]) if bounds else 0.,
                               max_value=float(bounds[1]) if bounds else None,
                               value=float(value) if value is not None else None,
                               step=1., key=f"{prefix}:{key}")
    return st.text_input(label(key), value=str(value) if value is not None else "",
                         key=f"{prefix}:{key}").strip() or None


def render_fields(fields, initial, prefix):
    columns = st.columns(3)
    values = {}
    for index, key in enumerate(fields):
        with columns[index % len(columns)]:
            values[key] = widget(key, initial, prefix)
    return values


def render_case(norm):
    case = norm["caso"]
    status = case["clasificacion"]
    badge = "Sin criterios suficientes" if status == "No cumple criterios / info insuficiente" else status
    st.badge(badge, color={"Confirmado": "green", "Probable": "orange", "Sospechoso": "blue"}.get(status, "gray"))
    st.caption(f'{case["referencia"]} · §6.1, pp. 24–25 (vulnerabilidad).')
    for title, entries in (("Criterios cumplidos", case["criterios_cumplidos"]),
                           ("Datos pendientes", case["datos_faltantes"])):
        if entries:
            st.markdown(f"**{title}**")
            for entry in entries:
                st.write(f"• {entry}")
    if norm["validacion"]["errores"]:
        st.warning(" · ".join(f"{label(key)}: {error}" for key, error in norm["validacion"]["errores"].items()))


def chart(fig):
    fig.update_layout(colorway=PALETTE, margin=dict(l=12, r=18, t=20, b=15))
    st.plotly_chart(fig, width="stretch")


def render_triage(result, prefix):
    norm = result["normativo"]
    st.subheader("Clasificación normativa")
    render_case(norm)
    left, right = st.columns(2)
    with left:
        priority = [PRIORITY[key] for key, flag in norm["vulnerabilidad"].items() if flag]
        st.write("**Prioridad sanitaria**")
        st.write(" · ".join(priority) if priority else "Sin prioridad documentada en la ficha.")
    with right:
        edi = norm["edi"]
        st.metric("Ingesta diaria estimada (µg MeHg/kg/día)",
                  "Sin datos suficientes" if edi["edi"] is None else f'{edi["edi"]:.3f}')
        if edi["edi"] is not None and edi["advertencia"]:
            st.caption(edi["advertencia"])
    st.subheader("Triaje predictivo · M1")
    st.info(EXPERIMENTAL)
    for col, (target, name) in zip(st.columns(len(TARGET_LABELS)), TARGET_LABELS.items(), strict=True):
        with col:
            risk = result["m1"][target]
            st.metric(name, f'{risk["probabilidad"]:.1%}')
            st.caption(f'Umbral val {risk["umbral"]:.1%} · ' + ("Alerta de triaje" if risk["alerta_triaje"] else "Sin alerta"))
    st.caption("Cordón umbilical sin modelo por ausencia de mediciones en la cohorte.")
    target = st.selectbox("Desenlace para explicación SHAP", tuple(TARGET_LABELS),
                          format_func=TARGET_LABELS.__getitem__, key=f"shap:{prefix}")
    shap = pd.DataFrame(result["m1"][target]["factores_modelo_independiente"])
    shap["Factor"] = shap["campo"].map(label)
    shap["Efecto"] = shap["contribucion_log_odds"].map(lambda value: "Aumenta" if value > 0 else
                                                       "Reduce" if value < 0 else "Neutro")
    chart(px.bar(shap.iloc[::-1], x="contribucion_log_odds", y="Factor", color="Efecto",
                 labels={"contribucion_log_odds": "Contribución al modelo independiente (log-odds)"},
                 color_discrete_map={"Aumenta": "#be6e3c", "Reduce": "#087f75", "Neutro": "#677e85"}))
    st.subheader("Fenotipo clínico · M3A")
    profile = result["m3a"]
    st.write("**" + (profile["perfil"] if profile["id"] >= 0 else "Fenotipo indeterminado / Atípico (-1)") + "**")
    distance = profile["distancia"]
    st.caption("Distancia al medoide más cercano: " + (f"{distance:.4f}" if distance is not None else
               "sin comparación admisible") + " · Radio P₉₀ · Cobertura mínima 0,50")
    biomarker = norm["biomarcador"]
    st.write("**Matriz biológica orientativa** · " + (" y ".join(biomarker["matrices"]) or "Por precisar"))
    st.caption(biomarker["orientacion"])


def triage_tab(cohort, examples, mode, artifacts):
    demo = None
    if mode == DEMO:
        name = st.selectbox("Caso de demostración", tuple(examples), key="demo_case")
        demo = examples[name]
        st.caption(f"Ficha sintética test · ID {demo}. Puedes editar los campos antes de evaluar.")
    prefix = f"triage:{demo or 'manual'}"
    initial = source_record(cohort.loc[demo]) if demo is not None else {}
    with st.form(prefix):
        record = {}
        for title, fields in (
            ("Demografía y vulnerabilidad materno-infantil", DEMOGRAPHICS),
            ("Exposición ocupacional y ambiental", EXPOSURE_FIELDS),
            ("Consumo íctico y temporalidad", DIET_TIME),
        ):
            with st.expander(title, expanded=fields is DEMOGRAPHICS):
                record.update(render_fields(fields, initial, prefix))
        with st.expander("Manifestaciones clínicas por sistema"):
            record.update(render_fields(CLINICAL_FIELDS, initial, prefix))
            for domain, indexes in DOMAINS.items():
                fields = [CLINICAL[index - 35] for index in indexes if CLINICAL[index - 35] not in record]
                if fields:
                    st.markdown(f"**{label(domain)}**")
                    record.update(render_fields(fields, initial, prefix))
        submitted = st.form_submit_button("Evaluar ficha", type="primary")
    active = st.session_state.get("triage_result")
    if submitted:
        active = {"context": prefix, "record": record, "demo": demo, "result": predict_patient(record, artifacts)}
        st.session_state["triage_result"] = active
        st.session_state.pop("lab_result", None)
        st.session_state["lab_source"] = ACTIVE_LAB
    if active and active["context"] == prefix:
        render_triage(active["result"], prefix)
        return active
    return None


def laboratory_record(record, panel, sample_date=None, delay=None, segment=None):
    """Conserva cada unidad declarada y adapta la demora al contrato de fechas."""
    result = dict(record)
    for matrix, (value, reported_unit, validated) in panel.items():
        key, _ = LAB_FIELDS[matrix]
        if value is not None:
            result[key] = value
            result[f"{key}_unidad"] = UNITS[reported_unit]
            result[f"{key}_validado"] = validated
            if matrix in {"Sangre", "Orina · masa de muestra"}:
                suffix = "sangre" if matrix == "Sangre" else "orina"
                result[f"laboratorio_{suffix}_validado"] = validated
    if sample_date:
        result["fecha_toma_muestra"] = sample_date.isoformat()
        if delay is not None:
            result["fecha_envio_lab"] = (sample_date + timedelta(days=delay)).isoformat()
    if segment is not None:
        result["EXT_67d_longitud_segmento_cabello_cm"] = segment
    return result


def render_laboratory(saved, artifacts):
    result = saved["result"]
    norm = result["normativo"]
    review = result["m3b"]
    st.subheader("Validación determinística y clasificación normativa")
    valid = norm["validacion"]["valido"]
    has_measurement = any(key in saved["record"] for key, _ in LAB_FIELDS.values())
    valid_status = ("Sin dosaje ingresado" if not has_measurement else
                    "Sin errores de unidad o consistencia detectados" if valid else "Hay errores en la ficha")
    st.badge(valid_status, color="teal" if valid and has_measurement else "gray" if valid else "red")
    render_case(norm)
    st.caption("Guía Técnica N.º 537 · §15.2, p. 36 · Cuadro 3, p. 32. "
               "Confirmación con sangre >20 µg/L y orina >50 µg/g, ambas validadas, y criterio clínico-epidemiológico.")
    st.subheader("Revisión estadística · M3B")
    if review["alerta_revision"]:
        st.warning(ALERT)
    elif review["elegible"]:
        st.info("Puntuación por debajo del umbral de revisión.")
    else:
        st.info("M3B sin puntuación. Requiere al menos una medición válida en la escala del modelo.")
    if review["elegible"]:
        cols = st.columns(2)
        cols[0].metric("Puntuación de anomalía", f'{review["puntaje"]:.3f}')
        cols[1].metric("Umbral calibrado en validación", f'{review["umbral"]:.3f}')
        if valid:
            features = transform_record(saved["record"], artifacts["transformers"])["m3b"]
            names = ("Cabello / exposición dietética", "Orina / exposición inhalatoria",
                     "Discordancia asintomática extrema", "Incoherencia matriz–vía")
            st.dataframe(pd.DataFrame({"Señal": names, "Variable": DISCORDANCE,
                                      "Entrada de M3B": [features[key] for key in DISCORDANCE]}),
                         hide_index=True)
            st.caption("Valores del vector que recibe el bosque. Una señal sin insumos puede usar la mediana de entrenamiento.")
        else:
            st.caption("Corrige los errores de la ficha para consultar las cuatro señales del registro completo.")
    st.table(pd.DataFrame([
        ("Validación determinística", "Verifica magnitud, unidad, rangos y consistencia de fechas."),
        ("Alerta estadística M3B", "Una discordancia requiere revisión técnica de la muestra y del registro."),
        ("Confirmación profesional", "El personal acredita la compatibilidad clínica y la validez de los dosajes."),
    ], columns=["Proceso", "Alcance"]))


def lab_tab(cohort, active, artifacts):
    sources = ([ACTIVE_LAB] if active else []) + ([TEST_LAB] if cohort is not None else [])
    st.subheader("Dosajes y condiciones de la muestra")
    st.caption("Registra cada resultado en su unidad original. La orina por masa de muestra y la orina ajustada "
               "por creatinina se capturan por separado. La validación declarada corresponde a revisión profesional.")
    if not sources:
        st.info("Evalúa una ficha en Triaje para habilitar la auditoría de laboratorio.")
        return
    source = st.radio("Fuente para laboratorio", sources, horizontal=True, key="lab_source")
    if source == ACTIVE_LAB:
        record = active["record"]
        selected = active["demo"]
        prefix = f"lab:active:{active['context']}"
    else:
        eligible = cohort.loc[cohort["split"].eq("test") & cohort[list(LAB)].notna().any(axis=1)]
        selected = st.selectbox("ID de ficha test con laboratorio", tuple(eligible.index), key="lab_test_id")
        record = source_record(cohort.loc[selected])
        prefix = f"lab:test:{selected}"
    initial = cohort.loc[selected].dropna().to_dict() if selected is not None else {}
    sample_date = day(initial.get("fecha_toma_muestra"))
    sent = day(initial.get("fecha_envio_lab"))
    delay = (sent - sample_date).days if sent and sample_date and sent >= sample_date else None
    with st.form(prefix):
        panel = {}
        for matrix, (key, default_unit) in LAB_FIELDS.items():
            st.markdown(f"**{matrix}**")
            a, b, c = st.columns(3)
            value = a.number_input(f"Concentración · {matrix}", value=initial.get(key), step=.01,
                                   format="%.4f", key=f"{prefix}:{key}:value")
            reported_unit = b.selectbox(f"Unidad · {matrix}", tuple(UNITS),
                                        index=tuple(UNITS).index(default_unit), key=f"{prefix}:{key}:unit")
            validated = c.checkbox(f"Resultado validado · {matrix}", key=f"{prefix}:{key}:validated")
            panel[matrix] = (value, reported_unit, validated)
        a, b, c = st.columns(3)
        sample = a.date_input("Fecha de toma", value=sample_date, key=f"{prefix}:sample")
        days = b.number_input("Demora de envío (días)", min_value=0, max_value=3650, value=delay, step=1,
                              key=f"{prefix}:delay")
        segment = c.number_input("Segmento capilar (cm)", min_value=0., value=initial.get(
            "EXT_67d_longitud_segmento_cabello_cm"), step=.1, key=f"{prefix}:segment")
        submitted = st.form_submit_button("Evaluar laboratorio", type="primary")
    if submitted:
        if days is not None and sample is None:
            st.warning("Indica la fecha de toma para aplicar la demora de envío.")
        augmented = laboratory_record(record, panel, sample, days, segment)
        st.session_state["lab_result"] = {"context": prefix, "record": augmented,
                                          "result": predict_patient(augmented, artifacts)}
    saved = st.session_state.get("lab_result")
    if saved and saved["context"] == prefix:
        render_laboratory(saved, artifacts)


@st.cache_data(show_spinner=False)
def population_summary(cohort):
    records = cohort.to_dict("records")
    classifications = pd.Series([classify_case(row)["clasificacion"] for row in records]).value_counts()
    priority = pd.DataFrame([assess_vulnerability(row) for row in records])
    summary = priority.apply(lambda values: values.eq(True).sum())
    maternal = priority[["embarazo", "lactancia", "mujer_edad_fertil", "menor_18"]].eq(True).any(axis=1).sum()
    return classifications, summary, maternal


def population_tab(cohort, audit, m3a, m3b):
    st.warning(SYNTHETIC)
    st.subheader("Panorama de la cohorte")
    a, b, c, d = st.columns(4)
    a.metric("Fichas sintéticas", f'{audit["n"]:,}'.replace(",", "."))
    c.metric("Con biomarcador elegible", f'{audit["lab_eligible_total"]:,}'.replace(",", "."))
    d.metric("Alertas M3B · test elegible", f'{m3b["test"]["alert_rate"]:.1%}')
    if cohort is None:
        b.metric("Prioridad materno-infantil", "Sin ficha local")
        st.info("Instala la ficha sintética para ver las distribuciones. Las métricas congeladas están disponibles.")
    else:
        classifications, priority, maternal = population_summary(cohort)
        b.metric("Prioridad materno-infantil registrada", f"{maternal / len(cohort):.1%}")
        left, right = st.columns(2)
        with left:
            st.markdown("**Clasificación normativa de las fichas**")
            labels = classifications.rename_axis("Estado").reset_index(name="Fichas")
            chart(px.bar(labels, x="Fichas", y="Estado", orientation="h"))
            st.caption("Aplicación directa de las reglas a la ficha sintética. La falta de dictamen o validación limita la confirmación.")
        with right:
            st.markdown("**Disponibilidad por matriz**")
            available = pd.DataFrame({"Matriz": ["Cabello", "Orina (Cr)", "Sangre"],
                                      "Fichas con medición": [int(cohort[key].notna().sum()) for key in LAB]})
            chart(px.bar(available, x="Matriz", y="Fichas con medición", color="Matriz"))
        st.dataframe(pd.DataFrame({"Prioridad": [PRIORITY[key] for key in priority.index],
                                   "Fichas": priority.to_numpy(), "Proporción de la cohorte": priority.to_numpy() / len(cohort)}),
                     hide_index=True, column_config={"Proporción de la cohorte": st.column_config.NumberColumn(format="percent")})
    st.subheader("Fenotipos y biomarcadores")
    counts = [{"Partición": label, "Perfil": "Atípico" if key == "-1" else f"Perfil {key}", "Fichas": value}
              for label, split_key in (("Validación", "validation_counts"), ("Prueba", "test_counts"))
              for key, value in m3a[split_key].items()]
    chart(px.bar(pd.DataFrame(counts), x="Perfil", y="Fichas", color="Partición", barmode="group"))
    assigned = [sum(value for key, value in m3a[split].items() if key != "-1")
                for split in ("validation_counts", "test_counts")]
    st.caption(f"Asignación por medoide · {assigned[0]}/225 en validación · {assigned[1]}/225 en prueba")
    split = st.radio("Partición para biomarcadores por perfil", ("validation", "test"),
                     format_func={"validation": "Validación", "test": "Prueba"}.__getitem__, horizontal=True)
    matrix = st.selectbox("Biomarcador por perfil", tuple(LAB),
                          format_func=dict(zip(LAB, ["Cabello (µg/g)", "Orina (µg/g Cr)", "Sangre (µg/L)"])).__getitem__)
    levels = [{"Perfil": "Atípico" if key == "-1" else f"Perfil {key}", "Mediana": values[matrix]["mediana"],
               "Mediciones": values[matrix]["n"]} for key, values in m3a["biomarcadores_externos"][split].items()]
    chart(px.bar(pd.DataFrame(levels), x="Perfil", y="Mediana", hover_data=["Mediciones"]))
    st.subheader("Métricas congeladas")
    st.success("M3B · 9 de 11 anomalías sintéticas detectadas en prueba (81,8 %), frente a 1 de 11 en la versión previa.")
    with st.expander("M1 · Métricas de prueba y auditoría de monotonía"):
        st.dataframe(pd.read_csv(REPORTS / "metrics_m1.csv"), hide_index=True)
        mono = read_json(REPORTS / "monotonicity_m1.json")
        st.dataframe(pd.DataFrame(mono).rename_axis("Corte superior").reset_index(), hide_index=True)
    with st.expander("M3A · Conteos, radios y biomarcadores externos"):
        st.dataframe(pd.DataFrame(counts), hide_index=True)
        st.dataframe(pd.Series(m3a["medoid_radii_p90"], name="Radio P₉₀").rename_axis("Perfil").reset_index(),
                     hide_index=True)
        st.dataframe(pd.DataFrame(levels), hide_index=True)
    with st.expander("M3B · Validación y prueba"):
        compact = pd.DataFrame({split: {name: value for name, value in m3b[split].items() if name != "confusion_matrix"}
                                for split in ("validation", "test")}).T
        st.dataframe(compact)
        for name, key in (("Validación", "validation"), ("Prueba", "test")):
            st.caption(f"{name} · Matriz de confusión")
            st.dataframe(pd.DataFrame(m3b[key]["confusion_matrix"], index=["Real normal", "Anomalía real"],
                                      columns=["Sin alerta", "Alerta"]))


def main(data_dir=DATA):
    st.set_page_config(page_title="Vigilancia de Mercurio · Bolivia", page_icon="🧪", layout="wide")
    st.html(HEADER)
    try:
        artifacts, manifest, digest = load_engine()
    except Exception as exc:
        st.sidebar.error("Verificación SHA-256 fallida")
        st.error(f"No se pudo cargar el backend congelado. {exc}")
        st.stop()
    with st.sidebar:
        st.success("Integridad SHA-256 verificada")
        st.caption("Huella de models/manifest.json")
        st.code(digest, language=None, wrap_lines=True)
        st.write(f"**Versión de esquema / contrato** · {manifest['contract_version']}")
        metrics = manifest["metrics"]
        urine = next(row for row in metrics["m1"]["test"]
                     if row["target"] == "y_hg_urinario_guia537" and row["modelo"] == "lightgbm")
        st.metric("M1 · Sensibilidad orina Guía 537 (test)", f'{urine["sensibilidad"]:.1%}')
        st.metric("M3A · Perfiles", metrics["m3a"]["clusters"])
        st.metric("M3B · Sensibilidad de anomalías (test)", f'{metrics["m3b"]["test"]["recall"]:.1%}')
        cohort = None
        examples = {}
        try:
            cohort = load_dashboard_data(data_dir)
            examples = pick_examples(cohort, artifacts, digest)
        except (OSError, ValueError) as exc:
            st.warning(f"Ficha sintética no disponible. {exc}")
        mode = st.radio("Modo de ingreso", [DEMO, MANUAL] if examples else [MANUAL], key="input_mode")
    triage, lab, population = st.tabs(["Triaje prelaboratorio", "Auditoría preanalítica", "Vigilancia poblacional"])
    with triage:
        active = triage_tab(cohort, examples, mode, artifacts)
    with lab:
        lab_tab(cohort, active, artifacts)
    with population:
        population_tab(cohort, read_json(REPORTS / "data_audit.json"), read_json(REPORTS / "metrics_m3a.json"),
                       read_json(REPORTS / "metrics_m3b.json"))


if __name__ == "__main__":
    main()
