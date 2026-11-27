# Acta de liberación — plantilla (sin ejecución)

Fecha: pendiente. Commit base/final: pendiente. SO/arquitectura/Python: pendiente. Huella manifiesto: pendiente. Responsable: pendiente. Todos los estados iniciales NOT_RUN. Usar PASS/FAIL/SKIP/NOT_RUN con evidencia y motivo. No marcar PASS sin ejecución real.

| Gate | Evidencia exigida | Estado | Ruta/observación |
|---|---|---|---|
| G0 | carga real, hashes, baseline y cohorte keyed verificada | NOT_RUN | — |
| G1 | cobertura y tipos, 82/11/30/63, 34 NLP; faltantes | NOT_RUN | — |
| G2 | captura manual, NLP, SQLite, recuperación, exportación segura | NOT_RUN | — |
| G3 | M1/SHAP/M3A/M3B reales, paridad y no fuga | NOT_RUN | — |
| G4 voz | Vosk real offline, transcripción editable, fallback | NOT_RUN | — |
| G4 territorio | DBSCAN y rutas verificadas, demanda no asignada | NOT_RUN | — |
| G5 | regresión, instalación limpia, prueba física, privacidad y backup | NOT_RUN | — |

## Comprobaciones finales
- [ ] git diff/status sin modificación de backend ni datos sensibles; hashes verificados.
- [ ] pip check y pytest baseline/final con XML; registrar passed/failed/skipped/error.
- [ ] M01: desconexión física, captura, reinicio, recuperación, edición y exportación.
- [ ] M02: grabación/transcripción local real si P1 disponible.
- [ ] M03: inferencia real, laboratorio, territorio/rutas si disponibles.
- [ ] M04: inspección de solicitudes y conexiones externas, localhost únicamente.
- [ ] PII, notas, firma, targets y latentes ausentes de payload analítico y exportación.
- [ ] Verificar respaldo SQLite y restauración en copia, integridad/FK.
- [ ] Bundle por SO/arquitectura, dependencias y recursos locales, arranque documentado.
- [ ] Demo ficticia, aviso experimental, no notificación oficial ni publicación.
- [ ] Reportar requisitos RF01–RF09 con evidencia, bloqueos y acciones pendientes.

## Clasificación
Completo: G0–G3/G5 PASS y P1 aprobados. Parcial demostrable: P0 PASS y P1 pendientes explícitos. Incompleto/no aceptado: cualquier P0 no superado. Sin prueba física: offline no verificado. Todos los estados son no aptos para uso clínico real. Sin autorización, no push, merge, alojamiento remoto ni cambio de visibilidad.

## Acta de pruebas
Por cada ID de TEST_PLAN: commit, entorno, fixture, esperado, observado, estado, evidencia, incidencia. Registrar duración real; no inventar SLA ni métricas. Si pruebas manuales fuera del entorno Codex, responsable humano completa acta. Documentar rollback de código y restauración de datos sin borrar registros existentes.
