"""Derivadas prelaboratorio de las secciones 2.1 y 2.2 del contrato."""
import calendar
from datetime import date

import numpy as np

from .contracts import CLINICAL
from .normative_engine import RULES, assess_vulnerability, day, number

DOMAINS = {
    "neurologico_motor": (53, 58, 59, 62), "neurologico_sensorial": (51, 61),
    "eretismo": (55, 56, 57), "cognitivo": (), "oral": (38, 39, 40, 41, 42, 43),
    "renal_clinico": (45, 54), "cutaneo": (46, 47, 48),
    "respiratorio_agudo": (52, 63, 64), "gastrointestinal": (35, 36, 37),
    "sintomas_inespecificos": (44, 49, 50),
}
AXES = {
    "neuromotor": (58, 59, 62), "sensorial": (51, 61), "neuropatia_periferica": (60, 61),
    "neuropsiquiatrico": (55, 56, 57), "oral_inorganico": DOMAINS["oral"],
    "respiratorio_inhalatorio": DOMAINS["respiratorio_agudo"], "renal": DOMAINS["renal_clinico"],
    "cutaneo": DOMAINS["cutaneo"], "gastrointestinal": DOMAINS["gastrointestinal"], "ocular": (49, 50, 51),
}
AXIS_EXPOSURE = ("eje_inhalatorio_ocupacional", "eje_dietetico", "eje_cronicidad",
                 "eje_recencia_inhalatoria", "eje_recencia_dietetica", "eje_exposicion_mixta",
                 "contraste_exposicion")
PHENOTYPES = ("P_Hg0", "P_MeHg", "D_clin", "M_clin")
EXPOSURE = ("antecedente_exposicion_hg", "via_respiratoria", "via_dermica", "via_oral",
            "tipo_ocupacional", "consumo_pescado_rio", "EXT_32b_especies_piscivoras_alto_hg",
            "EXT_27b_quema_amalgama_frecuencia", "EXT_27c_quema_espacio_cerrado_o_vivienda")
TEMPORAL = ("retardo_consulta_dias", "dias_desde_ultima_exposicion", "duracion_sintomas_dias",
            "duracion_exposicion_dias", "latencia_sintomatica_dias", "exposicion_continua",
            "flag_incoherencia_temporal")
BOUNDED_DERIVED = {*(f"indice_{key}" for key in DOMAINS), *(f"missingness_sindromico_{key}" for key in DOMAINS),
                   *(f"eje_{key}" for key in AXES), *AXIS_EXPOSURE, *PHENOTYPES,
                   "flag_convulsiones", "flag_hepatomegalia", "I_min", "I_max", "U",
                   "proporcion_sintomas_positivos", "proporcion_exposicion_evaluada",
                   "flag_informacion_contradictoria", "flag_incoherencia_temporal", "exposicion_continua"}


def _weighted(values):
    observed = [(value, weight) for value, weight in values if not np.isnan(value)]
    return sum(v * w for v, w in observed) / sum(w for _, w in observed) if observed else np.nan


def _date_range(value):
    exact = day(value)
    if exact:
        return exact, exact
    try:
        month = date.fromisoformat(f"{value}-01")
    except ValueError:
        return None
    return month, month.replace(day=calendar.monthrange(month.year, month.month)[1])


def _interval(later, earlier):
    return (later - earlier).days if later and earlier else np.nan


def _unit_interval(value, scale):
    return float(np.clip(value / scale, 0, 1))


def derive(record, row, half_lives):
    symptoms = {index: row[column] for index, column in enumerate(CLINICAL, 35)
                if str(record.get(column, "")).lower() != "no aplica"}
    observed = [value for value in symptoms.values() if not np.isnan(value)]
    count, total, positives = len(observed), len(symptoms), sum(observed)
    exposures = [row[key] for key in EXPOSURE if str(record.get(key, "")).lower() != "no aplica"]
    n_exp = sum(not np.isnan(v) for v in exposures)
    out = {
        "proporcion_sintomas_evaluados": count / total if total else np.nan,
        "indice_sindromico": positives / count if count else np.nan,
        "conteo_sintomas_presentes": positives,
        "conteo_sintomas_no_evaluados": total - count,
        "proporcion_sintomas_positivos": positives / count if count else np.nan,
        "conteo_desconoce_exposicion": len(exposures) - n_exp,
        "proporcion_exposicion_evaluada": n_exp / len(exposures) if exposures else np.nan,
        "I_min": positives / total if total else np.nan,
        "I_max": (positives + total - count) / total if total else np.nan,
        "U": (total - count) / total if total else np.nan,
    }
    weights = {38: 2, 40: 2, 55: 3, 56: 3, 57: 3, 59: 3, 61: 3, 62: 3}
    for name, ids in DOMAINS.items():
        values = [(symptoms[i], weights.get(i, 1)) for i in ids if i in symptoms]
        if name == "cognitivo":
            values = [(float(value) if value in (0, 1) else np.nan, weight)
                      for key, weight in (("clin_memoria", 2), ("clin_concentracion", 1))
                      if str(record.get(key, "")).lower() != "no aplica"
                      for value in [number(record.get(key))]]
        out[f"indice_{name}"] = _weighted(values)
        out[f"missingness_sindromico_{name}"] = (
            sum(np.isnan(v) for v, _ in values) / len(values) if values else np.nan)
    for name, ids in AXES.items():
        out[f"eje_{name}"] = _weighted([(symptoms[i], weights.get(i, 1)) for i in ids if i in symptoms])
    out["flag_convulsiones"], out["flag_hepatomegalia"] = row[CLINICAL[18]], row[CLINICAL[9]]

    freq, high, portion = (row[key] for key in ("frecuencia_consumo_pescado_dias",
        "EXT_32c_frecuencia_piscivoros_30d", "EXT_32d_tamano_porcion_gramos"))
    fish = RULES["fish_reference"]
    measured = number(record.get("concentracion_mehg_pescado_ug_g"))
    if freq == 0:
        load = 0.
    elif measured is not None and measured >= 0:
        load = freq * portion * measured
    elif 0 <= high <= freq:
        load = portion * fish["mehg_fraction"] * (
            high * fish["piscivorous_total_hg_ug_g"] + (freq - high) * fish["other_total_hg_ug_g"])
    else:
        load = np.nan
    weight = row["EXT_10b_peso_corporal_kg"]
    hours = row["tiempo_exposicion_horas_equiv"]
    burn = row["EXT_27b_quema_amalgama_frecuencia"]
    closed = row["EXT_27c_quema_espacio_cerrado_o_vivienda"]
    burn_hours = number(record.get("horas_quema_amalgama"))
    weighted_hours = hours * (1.35 if closed == 1 else 1.)  # [PE] multiplicador de recinto cerrado
    flags = assess_vulnerability(record)
    applicable = lambda name: float(flags[name]) if flags[name] is not None else np.nan
    routes = [value for value in (row["via_respiratoria"], row["tipo_ocupacional"])
              if not np.isnan(value)]
    inhalation = max(routes, default=np.nan)
    diet = _unit_interval(freq, 30)
    mixed = float(inhalation > 0 and freq > 0) if not np.isnan(inhalation + freq) else np.nan
    out.update(IC_30=load, EDI=load / (30 * weight) if weight > 0 else np.nan,
               embarazo_x_consumo_piscivoros=applicable("embarazo") * high,
               embarazo_x_quema_amalgama=applicable("embarazo") * burn,
               edad_fertil_x_quema_amalgama=applicable("mujer_edad_fertil") * burn,
               lactancia_x_carga_ictica=applicable("lactancia") * load,
               nino_x_consumo_pescado=applicable("menor_18") * freq,
               exposicion_mixta=mixed, exposicion_riberenia=row["consumo_pescado_rio"],
               tiempo_exposicion_laboral_horas=hours,
               horas_quema_amalgama=burn_hours if burn_hours is not None else (0. if burn == 0 else np.nan),
               quema_en_espacio_cerrado=closed,
               exposicion_domestica_indirecta=float(row["antecedente_familiar_mineria"] == 1 and row["tipo_ocupacional"] == 0)
                   if not np.isnan(row["antecedente_familiar_mineria"] + row["tipo_ocupacional"]) else np.nan,
               tiempo_exposicion_ponderado=weighted_hours,
               interaccion_neuro_dieta=out["eje_neuromotor"] * diet,
               interaccion_eretismo_ocupacional=out["indice_eretismo"] * inhalation,
               flag_informacion_contradictoria=int(high > freq or (freq > 0 and row["consumo_pescado_rio"] == 0)
                                                  or (closed == 1 and burn == 0)))

    reference = day(record.get("fecha_notificacion"))
    start = day(record.get("fecha_inicio_exposicion")) or day(record.get("fecha_exposicion"))
    onset = day(record.get("EXT_64b_fecha_inicio_sintomas"))
    last = _date_range(record.get("fecha_cese_exposicion")) or _date_range(record.get("fecha_exposicion"))
    active = number(record.get("exposicion_activa"))
    if active not in (0, 1):
        active = float(last[0] == reference and last[1] == reference) if reference and last else np.nan
    tmin, tmax = (_interval(reference, last[1]), _interval(reference, last[0])) if last else (np.nan, np.nan)
    elapsed = 0. if active == 1 else tmin if tmin == tmax and tmin >= 0 else np.nan
    symptom_days = _interval(reference, onset)
    duration = _interval(reference if active == 1 else (last[0] if last and last[0] == last[1] else None),
                         day(record.get("fecha_inicio_exposicion")))
    latency = _interval(onset, start)
    out.update(exposicion_activa=active, exposicion_continua=active,
               retardo_consulta_dias=symptom_days if symptom_days >= 0 else np.nan,
               dias_desde_ultima_exposicion=elapsed,
               duracion_sintomas_dias=symptom_days if symptom_days >= 0 else np.nan,
               duracion_exposicion_dias=duration if duration >= 0 else np.nan,
               latencia_sintomatica_dias=latency if latency >= 0 else np.nan,
               flag_incoherencia_temporal=int(tmax < 0 or symptom_days < 0 or duration < 0
                                               or (day(record.get("fecha_inicio_exposicion")) is not None and latency < 0)))
    for half in half_lives:
        key = f"recencia_{half:g}d"
        out[key] = 2 ** (-elapsed / half) if elapsed >= 0 else np.nan
        out[f"{key}_min"] = 1. if active == 1 else 2 ** (-tmax / half) if tmax >= 0 else np.nan
        out[f"{key}_max"] = 1. if active == 1 else 2 ** (-max(tmin, 0) / half) if tmax >= 0 else np.nan
    occ = _weighted([(inhalation, 1), (_unit_interval(hours, 160), 1)])
    out.update(eje_inhalatorio_ocupacional=occ, eje_dietetico=diet,
               eje_cronicidad=_unit_interval(row["antecedente_exposicion_anterior_anos"], 15),
               eje_recencia_inhalatoria=occ * out["recencia_90d"],
               eje_recencia_dietetica=diet * out["recencia_50d"],
               eje_exposicion_mixta=np.minimum(occ, diet), contraste_exposicion=occ - diet)
    p_hg0 = np.mean([out[f"eje_{key}"] for key in ("neuropsiquiatrico", "oral_inorganico",
                                                  "respiratorio_inhalatorio", "renal")])
    p_mehg = np.mean([out["eje_sensorial"], out["eje_neuromotor"]])
    out.update(P_Hg0=p_hg0, P_MeHg=p_mehg, D_clin=p_hg0 - p_mehg, M_clin=np.minimum(p_hg0, p_mehg))
    return out
