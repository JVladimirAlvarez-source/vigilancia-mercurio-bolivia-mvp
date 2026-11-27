# AGENTS.md — Vigilancia Inteligente de Mercurio, Bolivia

## Mandato
Construir el MVP offline de hackatón sobre el backend v2 existente. Solo datos ficticios. No es un dispositivo clínicamente validado. No publicar, desplegar remotamente, abrir túneles, enviar datos ni cambiar visibilidad sin autorización expresa. Trabajar en rama de desarrollo; no push ni merge a main sin autorización.

## Fuentes y precedencia
Baseline auditado: `56408ec57c98006cfc37df4e3fa3d5ce10867927`. Verificar HEAD y diferencias antes de actuar. Leer `docs/MVP_SPEC.md`, `docs/DATA_CONTRACT.md`, `app/capture_schema.json`, `docs/NLP_SPEC.md`, `docs/TERRITORIAL_SPEC.md`, `docs/UI_SPEC.md`, `docs/TEST_PLAN.md`, `docs/DEPLOYMENT.md`, `TASKS.md`. Los contratos reales `config/schema.json`, `config/feature_config.json`, `config/normative_rules.json` y código congelado gobiernan compatibilidad; la Guía 537 gobierna afirmaciones normativas. Si hay discrepancia, registrar bloqueo, no inventar ni corregir silenciosamente. Los 71 ítems históricos no equivalen a certificación normativa individual. No confundir convenciones MVP con normativa.

## Límites
- No modificar, agregar ni eliminar archivos de `src/`, `config/`, `models/`, `mercurio_mvp_v4/` ni reportes congelados; `load_artifacts()` verifica huellas incluso de nuevos .py/.json en src/config. No reentrenar, recalibrar, parchear manifiesto o eludir hashes.
- Cambios en app/, tests/, docs/, scripts/, .streamlit/, requisitos adicionales y .gitignore solo según TASKS. Mantener Python 3.12 y versiones del manifiesto; resolver nuevas dependencias en entorno aislado.
- M1 LightGBM/SHAP, M3A fenotipado y M3B auditoría existentes; M2 territorial y M3_NLP nuevos. Reutilizar predict_patient, transform_record, validate_record; no duplicar reglas clínicas. No tratar proxy urinario ajustado por creatinina como confirmación normativa.
- 82 columnas originales, 11 EXT_, 30 síntomas, 63 entradas prelab; comprobar identificadores y orden contra repo. No renombrar, inventar categorías, unidades o conversiones. Captura complementaria en app/capture_schema.json. Valores 0,1,null y estado semántico separados; preservar literal no aplica donde derive lo requiere. No usar No especificado para faltantes.
- SQLite local con UUID, FK, transacciones, versiones inmutables y control optimista. PII separada; no datos reales, audios, DB, exportaciones ni secretos en Git, logs o caché global. Lista positiva de inferencia y exportación; snapshots prelab; nunca introducir targets, latentes o laboratorio en M1. Pseudonimización no es anonimización.
- NLP determinístico español con 34 campos iniciales autorizados. Toda propuesta exige confirmación humana; negación, incertidumbre, temporalidad y sujeto. No ampliar a ocupación sin cambio aprobado del contrato. Dictamen clínico y validación lab exclusivamente profesionales. Vosk local opcional en fallo, no API remota.
- Territorio comunitario ficticio etiquetado; Haversine no es ruta vial. Conservar aislados y demanda no asignada. OR-Tools sin solución debe informar, no fabricar. No estimar tratamientos.
- Fallos IA no bloquean captura. Sin CDN, telemetría ni llamadas externas en operación; localhost 127.0.0.1. No afirmar notificación oficial, eficacia clínica o despliegue offline sin evidencia.

## Flujo obligatorio
Leer tarea y dependencias; inspeccionar archivos reales; ejecutar pruebas de baseline; implementar cambio mínimo con tests; ejecutar pruebas focalizadas y regresión; revisar git diff y git status; registrar evidencia PASS/FAIL/SKIP/NOT_RUN, comandos, entorno, cambios, limitaciones. No borrar assertions ni sustituir pruebas reales por mocks. No revertir trabajo ajeno. Un único integrador modifica app/app.py. Si falta dependencia, conservar capacidad manual y marcar requisito no completado. No declarar éxito por código generado. Consultar TEST_PLAN y RELEASE_CHECKLIST antes de liberar.
