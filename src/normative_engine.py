"""Validación y reglas determinísticas para el MVP de vigilancia."""
from datetime import date, datetime
from math import isfinite

from .contracts import CLINICAL, RULES, SCHEMA

ROUTES = ("via_respiratoria", "via_dermica", "via_oral", "via_desconocida")
EXPOSURE_TYPES = ("tipo_ocupacional", "tipo_accidental", "tipo_ambiental")
SAMPLES = dict(zip(("cabello", "orina", "sangre"), SCHEMA["lab_columns"]))
RESULT = "EXT_67b_concentracion_hg_resultado"
UNIT = "EXT_67c_unidad_medida"


def number(value):
    """Normaliza números finitos sin interpretar valores desconocidos como cero."""
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return value if isfinite(value) else None


def day(value):
    if missing(value):
        return None
    if isinstance(value, date):
        return value.date() if isinstance(value, datetime) else value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def missing(value):
    return value is None or str(value).strip().lower() in {"", "nan", "nat", "<na>", "desconoce", "no evaluado", "no aplica"}


def indicator(record, key, group, members):
    if not missing(record.get(key)):
        return number(record[key])
    if missing(record.get(group)):
        return None
    selected = {part.strip() for part in str(record[group]).split(";")}
    if selected == {"No especificado"}:
        return 0
    if selected and selected <= set(members):
        return int(key in selected)
    return None


def unit(value):
    return str(value).strip().lower().replace("µ", "u").replace("μ", "u").replace(" ", "")


def measurements(record):
    """Extrae mediciones numéricas no negativas, en las unidades del contrato."""
    values = {}
    for key, expected in SCHEMA["lab_units"].items():
        value = number(record.get(key))
        supplied_unit = record.get(f"{key}_unidad", expected)
        if value is not None and value >= 0 and unit(supplied_unit) == unit(expected):
            values[key] = value
    primary = SAMPLES.get(str(record.get("tipo_muestra", "")).strip().lower())
    result = number(record.get(RESULT))
    if primary and result is not None and result >= 0:
        if unit(record.get(UNIT)) == unit(SCHEMA["lab_units"][primary]):
            if primary not in values or values[primary] == result:
                values[primary] = result
            else:
                values.pop(primary)
    return values


def validate_record(record) -> dict:
    """Revisa tipos, rango, unidades, consistencia y orden de eventos."""
    errors = {}
    ranges = dict.fromkeys(SCHEMA["binary"], (0, 1)) | SCHEMA["ranges"]
    boolean_fields = ("procedencia_zona_riesgo_hg", "manifestacion_clinica_compatible",
                      "laboratorio_sangre_validado", "laboratorio_orina_validado")
    binary = set(SCHEMA["binary"]) | set(boolean_fields)
    ranges.update(dict.fromkeys(boolean_fields, (0, 1)))
    ranges.update(dict.fromkeys(SCHEMA["lab_columns"] + [
        RESULT, "lab_hg_orina_ug_g", "lab_hg_cordon_ug_l"], (0, float("inf"))))
    for key, (low, high) in ranges.items():
        raw = record.get(key)
        value = number(raw)
        if not missing(raw) and (value is None or not low <= value <= high
                                 or (key in binary and value not in (0, 1))):
            errors[key] = "valor fuera de rango o tipo inválido"
    dates = {key: day(record.get(key)) for key in SCHEMA["dates"]}
    for key, value in dates.items():
        raw_date = str(record.get(key))
        month_only = (key == "fecha_exposicion" and len(raw_date) == 7
                      and day(raw_date + "-01") is not None)
        if value is None and not missing(record.get(key)) and not month_only:
            errors[key] = "fecha inválida, se requiere AAAA-MM-DD"
    for first, second in (
        ("fecha_exposicion", "fecha_notificacion"),
        ("EXT_64b_fecha_inicio_sintomas", "fecha_notificacion"),
        ("fecha_exposicion", "fecha_toma_muestra"),
        ("fecha_toma_muestra", "fecha_envio_lab"),
    ):
        if dates[first] and dates[second] and dates[first] > dates[second]:
            errors[second] = f"fecha anterior a {first}"
    if not missing(record.get(RESULT)):
        key = SAMPLES.get(str(record.get("tipo_muestra", "")).strip().lower())
        dual_urine = key == "lab_hg_orina_ug_g_cr" and unit(record.get(UNIT)) == "ug/g"
        if dual_urine:
            key = "lab_hg_orina_ug_g"
        if not key or (not dual_urine and unit(record.get(UNIT)) != unit(SCHEMA["lab_units"][key])):
            errors[UNIT] = "unidad incompatible con la matriz biológica"
        elif not missing(record.get(key)) and number(record.get(key)) != number(record.get(RESULT)):
            errors[key] = "resultados contradictorios para la muestra principal"
    for key, expected in (SCHEMA["lab_units"] | {"lab_hg_orina_ug_g": "ug/g",
                                                "lab_hg_cordon_ug_l": "ug/L"}).items():
        if not missing(record.get(key)) and unit(record.get(f"{key}_unidad", expected)) != unit(expected):
            errors[key] = "unidad incompatible con la matriz biológica"
    fish_days = number(record.get("frecuencia_consumo_pescado_dias"))
    high_days = number(record.get("EXT_32c_frecuencia_piscivoros_30d"))
    if fish_days is not None and high_days is not None and high_days > fish_days:
        errors["EXT_32c_frecuencia_piscivoros_30d"] = "supera la frecuencia total"
    return {"valido": not errors, "errores": errors}


def classify_case(record) -> dict:
    """Evalúa §15.2 con dictamen clínico y dosajes validados independientes de ML."""
    validation = validate_record(record)
    criteria, needed = [], []
    epidemiology = RULES["epidemiology"]["any_of"]
    exposed = any(number(record.get(key)) == 1 for key in epidemiology)
    compatible = number(record.get("manifestacion_clinica_compatible"))
    if exposed:
        criteria.append("exposición confirmada o procedencia de zona de riesgo")
    else:
        needed.extend(key for key in epidemiology if missing(record.get(key)))
    if compatible == 1:
        criteria.append("manifestación aguda o crónica compatible, evaluada clínicamente")
        cardinal = {
            "eretismo": number(record.get("clin_eretismo")),
            "temblor": number(record.get("clin_62_temblor_distal")),
            "gingivitis": number(record.get("clin_38_gingivitis")),
        }
        criteria.extend(f"manifestación cardinal documentada: {name}"
                        for name in RULES["clinical"]["cardinal"] if cardinal[name] == 1)
    elif compatible is None:
        needed.append("manifestacion_clinica_compatible")

    classification = "No cumple criterios / info insuficiente"
    if exposed and compatible is None:
        classification = "Sospechoso"
    if exposed and compatible == 1:
        classification = "Probable"
        blood = measurements(record).get("lab_hg_sangre_ug_l")
        urine = number(record.get("lab_hg_orina_ug_g"))
        if (urine is None and str(record.get("tipo_muestra", "")).strip().lower() == "orina"
                and unit(record.get(UNIT)) == "ug/g"):
            urine = number(record.get(RESULT))
        thresholds = RULES["confirmation"]
        results = (
            ("sangre", blood, thresholds["blood_upper_ug_l"]),
            ("orina", urine, thresholds["urine_ug_g"]),
        )
        elevated = []
        for matrix, value, cutoff in results:
            validated = f"laboratorio_{matrix}_validado"
            if value is None:
                needed.append("lab_hg_sangre_ug_l" if matrix == "sangre" else "lab_hg_orina_ug_g")
            elif number(record.get(validated)) != 1:
                needed.append(validated)
            elif value > cutoff:
                criteria.append(f"dosaje validado de {matrix} por encima de la referencia")
                elevated.append(matrix)
        if len(elevated) == len(results) and validation["valido"]:
            classification = "Confirmado"
    needed.extend(key for key in validation["errores"] if key not in needed)
    return {"clasificacion": classification, "criterios_cumplidos": criteria,
            "datos_faltantes": needed, "referencia": RULES["reference"]}


def calculate_edi(record) -> dict:
    """Calcula la ingesta en µg/kg/día con consumo y peso declarados."""
    weight = number(record.get("EXT_10b_peso_corporal_kg"))
    freq = number(record.get("frecuencia_consumo_pescado_dias"))
    portion = number(record.get("EXT_32d_tamano_porcion_gramos"))
    intake = number(record.get("ingesta_pescado_g_dia"))
    concentration = number(record.get("concentracion_mehg_pescado_ug_g"))
    measured = not missing(record.get("concentracion_mehg_pescado_ug_g"))
    reference = RULES["fish_reference"]
    high = number(record.get("EXT_32c_frecuencia_piscivoros_30d"))
    if intake is None and freq is not None and 0 <= freq <= 30:
        if freq == 0:
            intake = 0.0
        elif portion is not None and portion >= 0:
            intake = freq * portion / 30
    if not measured and freq is not None and freq > 0 and high is not None and 0 <= high <= freq:
        fraction = high / freq
        concentration = reference["mehg_fraction"] * (
            fraction * reference["piscivorous_total_hg_ug_g"]
            + (1 - fraction) * reference["other_total_hg_ug_g"])
    value = None
    if weight is not None and weight > 0 and intake is not None and intake >= 0:
        if intake == 0:
            value = 0.0
        elif concentration is not None and concentration >= 0:
            value = concentration * intake / weight
    return {"edi": value, "unidad": "µg/kg/día", "referencial": not measured and intake != 0,
            "advertencia": None if measured or intake == 0 else reference["source"]}


def assess_vulnerability(record) -> dict:
    """Devuelve banderas independientes, con None para datos desconocidos."""
    age = number(record.get("edad"))
    sex = str(record.get("sexo", "")).upper()
    low, high = RULES["fertile_age_years"]

    def flag(key):
        value = number(record.get(key))
        return bool(value) if value in (0, 1) else None

    return {"embarazo": flag("embarazo_actual"), "lactancia": flag("lactancia_actual"),
            "mujer_edad_fertil": (sex == "F" and low <= age <= high)
            if sex in {"F", "M"} and age is not None else None,
            "menor_18": age < 18 if age is not None and 0 <= age <= 120 else None,
            "exposicion_fetal": flag("embarazo_actual"),
            "exposicion_cronica_sistematica": flag("exposicion_cronica_sistematica")}


def recommend_biomarker(record) -> dict:
    """Orienta el muestreo según exposición ocupacional y dieta crónica."""
    occupational = indicator(record, "tipo_ocupacional", "tipo_exposicion", EXPOSURE_TYPES) == 1
    respiratory = indicator(record, "via_respiratoria", "via_exposicion", ROUTES) == 1
    diet = number(record.get("consumo_pescado_rio")) == 1
    chronic = record.get("exposicion_dietetica_cronica") is True or (
        (number(record.get("frecuencia_consumo_pescado_dias")) or 0) > 0
        and record.get("exposicion_dietetica_cronica") is not False)
    matrices = (["Orina"] if occupational or respiratory else []) + (["Cabello"] if diet and chronic else [])
    return {"matrices": matrices, "orientacion": (
        "Orina para exposición elemental o inorgánica. Cabello para exposición dietética crónica."
        if matrices else "Precisar vía y temporalidad antes de orientar el muestreo.")}
