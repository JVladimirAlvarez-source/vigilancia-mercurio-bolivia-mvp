# TASKS — Backlog ejecutable y dependencias

Estado inicial de todas las tareas: NOT_RUN. Presupuesto de seis horas, no garantía. P0 obligatorio; P1 objetivos de demo con degradación explícita; P2 fuera de alcance. Cada tarea entrega diff, tests y evidencia en data/local/qa/ (ignorado). No cambiar backend congelado. Rutas nuevas son propuestas de implementación.

| ID | Prioridad | Dependencias | Responsable | Archivos propios | Entrega y aceptación |
|---|---|---|---|---|---|
| T00 | P0 | — | Integrador | ninguno de backend; evidencia QA local | HEAD, versiones, hashes, baseline pytest, carga real; regenerar keyed solo en destino limpio y comprobar manifiesto. G0/B01–B03. |
| T01 | P0 | T00 | Integrador | app/capture_schema.json, app/capture_contract.py, tests/test_contract.py | Verificar 82/11/30/63 y 20 adicionales; resolver discrepancias sin inventar; 34 NLP autorizados. G1/C01–C07. |
| T02 | P0 | T01 | A | app/storage.py, tests/test_storage.py | Ocho tablas del DATA_CONTRACT, versiones, transacciones, privacidad, backup; D01–D06. |
| T03 | P0 | T01,T02 | A | app/capture.py, tests/test_capture.py | Editor completo, estado aislado, validación, guardado y recuperación, sin widgets duplicados. C01–C07/U pertinentes. |
| T04 | P0 | T01 | B | app/nlp_engine.py, app/nlp_patterns.json, tests/test_nlp.py | extract_entities/review_proposals según NLP_SPEC, N01–N17, sin escrituras directas. |
| T05 | P1 | T04 | B | app/speech_to_text.py, tests/test_speech.py | Vosk local, texto editable, límites de audio, V01–V02; fallback explícito. |
| T06 | P0 | T02,T03,T04 | Integrador | app/inference_adapter.py, app/exporter.py, app/app.py, tests/test_integration.py, tests/test_exporter.py, tests/test_app.py | Integrar captura/NLP y backend existente; I01–I07/E01–E02/U; conservar pestañas y pruebas clínicas. |
| T07 | P1 | T01,T02 | C | app/territorial.py, tests/test_territorial.py, fixtures ficticios bajo tests/ | Contratos comunitarios, DBSCAN, OR-Tools, demanda e insumos; T01–T06 de TEST_PLAN (IDs de pruebas, no tareas). |
| T08 | P0 | T06; T05/T07 si disponibles | Integrador | app/app.py (integración final), requirements-offline.txt, scripts/setup_offline.py, scripts/start_offline.py, .streamlit/config.toml, .gitignore, app/README.md | Resolver dependencias, integrar P1 aprobados, wheelhouse por plataforma, localhost, recuperación. No descarga en ejecución. |
| T09 | P0 | T08 | QA/integrador | docs/RELEASE_CHECKLIST.md (solo resultado si autorizado), evidencia QA local | G0–G5, regresión, M01–M04, informe y clasificación de release; no publicar. |

## Interfaces a congelar en T01
Usar los contratos exactos de los documentos, no inferir firmas solo por nombres. Acordar estructuras de entrada/salida, errores tipados, unidades y dependencias de módulos antes de paralelizar. Validar con fixtures compartidos. El adaptador de inferencia incluye contexto explícito de derive y motor normativo, no solo PRELAB. La selección de panel lab debe resolver ambigüedad explícitamente. La interfaz debe guardar aun si load_artifacts falla.

## Bloqueos conocidos
- Datos keyed y hashes aún no comprobados en ejecución. No anexar IDs por posición.
- Vocabularios entrenados y periodo de quema requieren inspección real. No inventar reglas de normalización. Si no se puede resolver, conservar original y omitir proyección ambigua.
- Correspondencia normativa por ítem pendiente; no certificar. NLP ocupacional pendiente de aprobación de allowlist; registrar texto como observación restringida, no inferir exposición.
- Coordenadas y logística reales ausentes: fixtures ficticios únicamente. Equipo destino y disponibilidad de wheels/voz pendientes.

## Definition of Done por tarea
Implementación + pruebas nuevas + regresión pertinente + evidencia reproducible + diff limitado + reporte de bloqueos. Si un requisito P0 queda bloqueado, no etiquetar release aceptado. No hacer commit/push/merge salvo autorización. Si no hay agentes paralelos, ejecutar T00→T01→T02→T03→T04→T06→T05→T07→T08→T09, priorizando pruebas P0.
