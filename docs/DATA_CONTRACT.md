# Contrato de datos — captura offline v0.1.0

Estado: propuesta de ingeniería para Codex. Contrato backend v2, commit `56408ec57c98006cfc37df4e3fa3d5ce10867927`. `app/capture_schema.json` enumera 82 campos de captura (11 EXT_, 30 clínicos), más campos operativos ya consumidos. Los 71 restantes son el esquema histórico del proyecto, no una certificación independiente de correspondencia normativa individual.

## Invariantes
- El identificador exacto del repo es la clave de cada valor. Mantener orden de `SCHEMA['raw_columns']` en exportación autorizada, sin renombrar. `PRELAB_ALLOWLIST` tiene 63 entradas (56 directas + 7 indicadores de exposición). Comprobar conjuntos y orden contra los archivos reales mediante pruebas; no confundir allowlist con columnas finales seleccionadas por modelo.
- Las extensiones EXT_ son científicas, los campos operativos no son nuevos ítems oficiales. Los metadatos nuevos se almacenan fuera del registro de inferencia.
- No usar `row_id` de cohorte como identidad clínica. Crear UUID de paciente y caso, independientes, y conservar row_id solo para demostraciones sintéticas identificadas como tales.
- Todo valor de captura puede faltar durante borrador. Fecha de notificación para finalizar es regla operativa propuesta; la falta de CI o teléfono no bloquea registro.

## Persistencia propuesta (SQLite)
Ruta `data/local/vigilancia.db`, excluida de Git por regla existente `/data/`. Activar foreign_keys en cada conexión, usar consultas parametrizadas, transacciones atómicas y timeout de escritura. No usar caché global de datos de pacientes. Esquema lógico:

| Tabla | Clave y columnas mínimas | Restricciones |
|---|---|---|
| patients_private | patient_id TEXT PK, identity_json TEXT, created_at TEXT | Acceso restringido; no exportación analítica |
| cases | case_id TEXT PK, patient_id TEXT FK, created_at TEXT, current_version INTEGER, record_status TEXT | Estados draft, validated, archived; exportación y evaluación son eventos separados |
| case_versions | case_id FK, version INTEGER, payload_json TEXT, field_status_json TEXT, provenance_json TEXT, updated_at TEXT, schema_version TEXT | PK(case_id,version); instantáneas inmutables; sin PII directa |
| case_private | case_id FK, version INTEGER, private_json TEXT | FK compuesta a versión; observaciones, residencia detallada, notificador, firma; PII no repetida en payload |
| lab_results | lab_id TEXT PK, case_id FK, case_version INTEGER, matrix TEXT, value REAL NULL, unit TEXT NULL, sample_date TEXT NULL, sent_date TEXT NULL, validated INTEGER NULL | Unidad original; validación 0/1/null; conservar resultados separados por muestra |
| predictions | prediction_id TEXT PK, case_id FK, case_version INTEGER, input_snapshot_json TEXT, manifest_sha256 TEXT, result_json TEXT, created_at TEXT | FK compuesta; snapshot prelaboratorio sin PII; no sobrescribir triaje histórico |
| territorial_data | geo_id TEXT PK, case_id FK, community_label TEXT, latitude REAL NULL, longitude REAL NULL, source TEXT, scope TEXT, accuracy_m REAL NULL | coordenadas comunitarias, no domicilio; rangos ±90/±180 |
| audit_log | event_id TEXT PK, case_id FK, version INTEGER, action TEXT, created_at TEXT, metadata_json TEXT | No texto clínico ni valores personales en log |

Guardar identidad, versión, datos privados y auditoría en una transacción. Usar control optimista de versión para impedir pérdida de ediciones. No eliminar automáticamente duplicados; advertir. Guardar timestamps UTC ISO-8601 con zona horaria y fechas clínicas locales como fecha ISO. JSON estricto (allow_nan=False); NaN se convierte a null solo al serializar. No persistir audio por defecto; notas/transcripciones sensibles en área restringida únicamente si son necesarias. SQLite sin cifrado no es suficiente para producción; solo datos ficticios. Restringir permisos del archivo, excluir DB, WAL, backups y exportaciones de Git. No exposición de red pública.

## Faltantes y procedencia
`field_status`: observed, unknown, not_recorded, not_evaluated, not_applicable, pending, refused. Valor observado binario = 0 o 1; los demás valores = null con motivo separado. El adaptador traduce not_applicable al literal `no aplica` cuando el backend lo distingue (por ejemplo CLINICAL); no cambiar denominadores de `derive()` inadvertidamente. Ninguna opción de formulario se inicializa a No. Cero de laboratorio medido es distinto de ausencia. Cada campo modificado conserva fuente manual/nlp_text/nlp_voice/import, hora y estado de revisión. Evidencia textual sensible no entra en logs ni predictores.

## Adaptador de inferencia
1. Leer versión de ficha y validaciones; excluir PII, metadatos, geografía detallada, targets, auditoría latente y notas. Lista positiva de claves: PRELAB, contexto prelab que consume derive(), campos normativos explícitos, y laboratorio solo cuando corresponda. Revisar contexto exacto con `src/derived_features.py` y `src/normative_engine.py`. No pasar todo el JSON sin filtrar.
2. Mantener códigos categóricos entrenados (`artifacts['transformers']['m1']`); registrar etiqueta original desconocida y permitir NaN por transformador, sin asignar índice nuevo. Fechas incompletas conservar precisión; no fabricar día.
3. Para `via_exposicion` y `tipo_exposicion`, usar indicadores individuales 0/1/null cuando evaluación parcial; conservar grupo original en captura. No enviar grupo `No especificado` para faltantes: `indicator()` lo interpreta como 0. Evitar grupo contradictorio con indicadores; otra vía/tipo se conserva como texto complementario sin inventar predictor. Probar que indicadores faltantes no caigan a cero por fallback del grupo.
4. Validar mediante `validate_record()`. No borrar dato original; conservar errores. No ejecutar predicción de ficha inválida hasta corregir o confirmar tratamiento de exclusiones. Dictamen `manifestacion_clinica_compatible` y validaciones lab solo profesionales. No derivar automáticamente de NLP. Revisar que concentración en pescado, si usada como entrada, sea disponible antes de evaluación y documentada, no inferida desde laboratorio del paciente.
5. Llamar `predict_patient()` con artefactos verificados. No reimplementar transformadores ni ajustar en inferencia. Guardar instantánea prelaboratorio y salida M1 con versión y huella; posterior auditoría usa registro actualizado y no reemplaza predicción original. M3B solo con medición elegible en escala de modelo.

## Unidades y convenciones
`edad` en años según backend, preservar valor/unidad original de lactante y no forzar a cero; edad fraccional queda sujeta a revisión de compatibilidad del modelo. `tiempo_exposicion_horas_equiv` requiere valor/unidad originales y conversión documentada; no interpretar años laborales como horas continuas ni aproximar meses sin regla aprobada. `frecuencia_consumo_pescado_dias` usa días/30 por contrato, no mandato de guía; no multiplicar automáticamente frecuencia semanal. `EXT_27b_quema_amalgama_frecuencia` requiere confirmar periodo del simulador antes de normalizar. Número de hijos entero >=0; rangos existentes son límites del modelo, no censura clínica: conservar valor original y marcar fuera de dominio. CI y teléfono texto, sin regex oficial inventada. Fechas inusuales se conservan; errores existentes del backend se muestran, no se silencian.

Laboratorio: `lab_hg_cabello_ug_g` ug/g; `lab_hg_orina_ug_g_cr` ug/g Cr; `lab_hg_sangre_ug_l` ug/L; `lab_hg_orina_ug_g` ug/g; `lab_hg_cordon_ug_l` ug/L (no modelo de cordón). Conservar `*_unidad` cuando se proyecta, no convertir masa a creatinina sin datos. Resolver explícitamente la selección de muestra principal si existen varias; si contradicción o ambigüedad, bloquear evaluación de ese panel y solicitar revisión. `y_hg_urinario_guia537` es proxy sintético en ug/g Cr, no confirmación oficial. `EXT_67b...` nunca es predictor M1.

## NLP y territorio
El extractor devuelve lista de propuestas: field_id, proposed_value, evidence, assertion, temporality, experiencer, source, review_status. No aplica mutaciones directamente; solo propuesta presente/negada contextualizada y aceptada por usuario. Incertidumbre, pasado o tercero quedan pendientes; conflicto no sobrescribe. Cefalea no existe entre 30 síntomas oficiales del repo; preservar en observaciones restringidas. Aliases iniciales son propuestas no validadas. Usar lista permitida de campos NLP definida en schema. Voz transcribe localmente y permite editar antes de extracción.

Territorio usa comunidad/establecimiento y coordenadas ficticias etiquetadas, con fuente, precisión y alcance. Agregar vulnerabilidad por comunidad y resultado de triaje con aviso experimental. No exportar coordenadas de domicilios ni publicar grupos pequeños identificables; para hackatón solo ficción. DBSCAN conserva ruido como demanda aislada. Distancia Haversine no es tiempo vial; OR-Tools recibe matriz local, capacidad y punto de partida explícitos. Insumos estimados por protocolos o parámetros ficticios, no cantidades clínicas exactas.

## Exportación y pruebas
CSV/JSON analítico: lista positiva de variables aprobadas, sin identidad, firma, notas, identificadores de terceros ni ubicación fina; pseudonimización no equivale a anonimización. JSON incluye versión de contrato y timestamp; CSV vacío para faltante, archivo complementario de motivos si requerido. No mezclar casos nuevos con dataset de entrenamiento. No exportar targets inventados. Exportación oficial no se implementa hasta acordar destino institucional, autenticación y formato.

Pruebas obligatorias: igualdad ordenada de raw_columns, 11 EXT_, 30 clínicas, 63 entradas prelab; unicidad IDs; ida/vuelta 0/1/null/no aplica; multiselección parcial; categorías desconocidas; PII ausente del payload de inferencia/exportación; fechas y unidades inválidas; recuperación de SQLite y rollback; versiones inmutables; NLP negación/incertidumbre/tercero/conflicto; M1 invariante ante añadir solo datos lab; M3B no elegible sin dosaje; hash intacto; pruebas previas y desconexión real. El código de pruebas existente espera tres pestañas y prohíbe ajuste en interfaz: adaptar assertions de navegación solo de forma justificada, no eliminar comprobaciones de seguridad.

## Decisiones pendientes antes de uso real
Correspondencia ítem por ítem con páginas 36–37, catálogos oficiales, semántica de frecuencia de quema y duración, campos «Otro», manejo de edad infantil, validación clínica externa, cifrado y acceso, notificación y sincronización institucional. No resolver por suposición silenciosa.
