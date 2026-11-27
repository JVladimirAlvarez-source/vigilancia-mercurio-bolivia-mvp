# NLP_SPEC — Asistente de captura offline (M3_NLP)
Versión 0.1.0 | Estado: especificación candidata, no implementación | Base backend v2, commit 56408ec57c98006cfc37df4e3fa3d5ce10867927.

## 1. Alcance y dependencias
RF03 (P0): extracción textual en español; RF06 (P1): voz local. No es diagnóstico ni LLM generativo. Fuentes: `app/capture_schema.json`, `docs/DATA_CONTRACT.md`, `docs/MVP_SPEC.md`. La lista positiva actual permite exactamente 34 campos: 30 `clin_35` a `clin_64`, `edad`, `embarazo_actual`, `lactancia_actual`, `consumo_pescado_rio` (30+4). Cualquier ampliación exige cambio explícito y revisado en capture_schema. Ocupación, frecuencia dietética, exposición confirmada, campos operativos, laboratorio, PII y dictamen profesional están deshabilitados en la versión actual. No confundir M3_NLP con M3A/M3B.

Archivos nuevos: `app/nlp_engine.py`, `app/nlp_patterns.json`, `app/speech_to_text.py`, `tests/test_nlp.py`, `tests/test_speech.py`. El integrador modifica `app/app.py` y `app/capture.py`. No tocar `src/`, `config/`, artefactos ni manifiesto. Usar spaCy blank('es'), sentencizer, Matcher/PhraseMatcher y regex; sin descargas durante ejecución. Dependencias compatibles con manifiesto, verificadas antes de instalar. Vosk español local opcional; ruta configurable fuera de directorios congelados, por ejemplo `data/local_assets/vosk-es/`.

## 2. Interfaces propuestas
`extract_entities(text: str, schema: dict, source: str) -> list[dict]`: función pura, sin SQLite ni Streamlit. `source` enum nlp_text/nlp_voice. `review_proposals(proposals, decisions, current_record, expected_version) -> patch`: devuelve cambios y conflictos, nunca escribe. `transcribe_audio(wav_bytes, model_dir) -> dict`: devuelve text, status, error_code; no persistencia de audio. Errores explícitos: EMPTY_TEXT, INPUT_TOO_LONG, MODEL_MISSING, INVALID_AUDIO, TRANSCRIPTION_FAILED. Sin llamadas remotas ni fallbacks cloud.

Cada propuesta incluye `proposal_id` (UUID), `field_id`, `proposed_value` (tipo exacto o null), `evidence`, `span_start`, `span_end` (offsets Unicode en texto original, fin exclusivo), `assertion` (affirmed/negated/uncertain/conflict), `temporality` (current/historical/unknown), `experiencer` (patient/other/unknown), `source`, `review_status` (pending/accepted/rejected), `reason_code`, `rule_id`, `rules_version`. No confianza numérica inventada. Evidencia y texto son sensibles; solo sesión o área restringida, jamás log/CSV/ML.

## 3. Procesamiento determinístico
1. Validar texto no vacío, máximo operativo 4000 caracteres; no truncar silenciosamente. Mantener original y offsets; normalización acentos/case solo para comparar.
2. Cargar aliases de los campos con `nlp_mode=proposal`; patrones adicionales deben apuntar a esos IDs. Comparar tokens completos, resolver coincidencias solapadas con la más específica. Validar el diccionario al iniciar.
3. Delimitar oración y cláusula (puntuación, pero/sin embargo); reglas de negación antes del concepto (niega, no presenta, sin) y coordinación (ni). No extender negación a cláusula afirmativa siguiente. Doble negación o alcance dudoso => uncertain.
4. Marcar incertidumbre (posible, sospecha, podría), pasado (antecedente, tuvo, hace años), sujeto ajeno (madre, hijo, familiar). Si sujeto o temporalidad ambiguos, no convertir a presencia confirmada. No inferir que ausencia de mención es ausencia clínica.
5. Edad: patrón explícito paciente de N años / N años de edad; aceptar solo valor 0–120 años; meses/días a revisión manual, nunca cero por defecto. No tomar edad del familiar. Embarazo/lactancia y consumo de pescado: requerir relación explícita con paciente; mera mención de pescado no basta. Frecuencia semanal permanece sin extracción estructurada. Temblor genérico no equivale necesariamente a temblor distal; cefalea no existe en esquema, conservar nota restringida.
6. Consolidar por field_id: duplicados concordantes se agrupan con evidencia; afirmación y negación incompatibles => conflict y null. Históricos/terceros/inciertos se muestran informativamente sin patch automático.
7. Revisar propuestas antes de aplicarlas. Solo afirmación/negación actuales del paciente o número explícito y válido son aceptables; el resto requiere edición manual independiente. Toda propuesta aceptada debe cumplir tipo/rango del esquema. Si dato observado distinto, exigir decisión explícita de reemplazo y versión vigente. Rechazo no cambia ficha. Confirmación no equivale a dictamen clínico.

## 4. Voz
Grabación breve WAV PCM mono 16-bit 16 kHz (convertir localmente si existe conversor instalado; de otro modo informar formato requerido); límite propuesto 60 s / 5 MiB. Vosk cargado una vez; no almacenar audio por defecto. Mostrar transcripción editable y botón separado de extracción; no ejecutar automáticamente con cada rerun. Si falta micrófono/modelo o audio es ilegible, texto/manual siguen activos. No afirmar reconocimiento de idiomas indígenas ni rendimiento clínico. No almacenar voz ni texto en caché global; no usar información real en demo.

## 5. Casos de aceptación mínimos (fixtures ficticios)
| ID | Texto | Resultado esperado |
|---|---|---|
| N01 | Paciente de 28 años, embarazada. Presenta náuseas. | edad=28, embarazo_actual=1, clin_35_nauseas=1, propuestas pendientes |
| N02 | Niega náuseas y vómito. | clin_35_nauseas=0, clin_36_vomito=0 |
| N03 | Niega náuseas, pero presenta tos. | náuseas=0, clin_64_tos=1 |
| N04 | Posible ataxia. | clin_59_ataxia incierto, sin patch |
| N05 | Su madre presenta temblor distal. | clin_62_temblor_distal tercero, sin patch |
| N06 | Tuvo gingivitis hace años. | clin_38_gingivitis histórico, sin patch |
| N07 | Niega tos. Presenta tos. | conflicto, sin patch |
| N08 | Trabaja en minería. Cefalea. | no inventar campo ni exposición confirmada |
| N09 | Consume pescado de río cuatro días por semana. | consumo_pescado_rio=1; frecuencia no extraída |
| N10 | Paciente de 8 meses. | no normalizar edad sin revisión |
| N11 | Paciente sin náuseas. | propuesta 0 no confundida con null |
| N12 | Madre de 30 años, paciente de 7 años. | edad paciente=7 o revisión si ambigüedad, nunca 30 |
| N13 | texto vacío / modelo ausente | error explícito y captura manual disponible |
| N14 | dato confirmado 1 y propuesta 0 | conflicto; no sobrescribir sin decisión explícita |

Pruebas por cada alias canónico de 30 síntomas, offsets con acentos, entradas fuera de rango, reglas de ámbito y allowlist. Reportar TP/FP/FN, precision/recall/F1 micro y por campo (sin soporte => no evaluable); medir por separado errores de contexto. Fixtures de desarrollo y evaluación separados; cero modificaciones prohibidas y 100% de casos críticos anteriores como puerta P0; no extrapolar a clínica. Voz: WER=(S+D+I)/N en clips con referencia manual; reportar errores en términos clínicos y negaciones. Prueba real sin Internet para afirmar voz offline. Si falta Vosk, etiquetar RF06 no completado.
