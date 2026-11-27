# TEST_PLAN — Calidad, regresión y aceptación offline
Versión 0.1.0 | Especificación candidata, no informe de ejecución | Base: contrato v2, commit 56408ec57c98006cfc37df4e3fa3d5ce10867927.

## 1. Alcance y fuentes
Aplicar MVP_SPEC, DATA_CONTRACT, capture_schema.json, NLP_SPEC, TERRITORIAL_SPEC y UI_SPEC. Solo datos ficticios. Las pruebas verifican funcionamiento técnico, no eficacia clínica ni certificación normativa. P0 obligatorio; P1 objetivo de demo, fallo explícito y degradación; P2 fuera del alcance. No alterar src/, config/, models/ ni manifiesto para hacer pasar pruebas. No entrenar en interfaz. Si la rama cambió, comparar contra la base y documentar discrepancias antes de editar. Guardar evidencia local sin PII en data/local/qa/.

## 2. Puertas de calidad
| Puerta | Requisito | Evidencia | Si falla |
|---|---|---|---|
| G0 baseline | Python 3.12, dependencias, hashes y pruebas previas | commit, pip freeze, salida pytest y carga | preservar diagnóstico; no ocultar fallos ni alterar hashes |
| G1 contrato | 82 campos originales, 11 EXT_, 30 clínicos, 20 adicionales y 63 entradas prelab; roles y faltantes | test_capture | bloquear integración de campo discrepante |
| G2 captura | SQLite, versionado, revisión NLP y exportación | test_storage, test_nlp, test_capture | P0 no liberable |
| G3 inferencia | M1/M3A/M3B intactos, separación temporal | regresión y pruebas de integración | captura autónoma; RF04 no completado |
| G4 módulos P1 | voz, territorio, rutas | resultados reales y limitaciones | declarar no completado sin bloquear P0 |
| G5 release | operación física offline, recuperación, ausencia de exposición externa | acta de prueba manual | no declarar offline verificado ni release completo |

## 3. Matriz de pruebas ejecutables
Los nombres de archivos nuevos son propuestas; conservar las pruebas originales. Cada fila requiere al menos un caso automatizado, salvo M (manual). Pruebas con tmp_path y fixtures ficticios; ninguna escribe sobre data/ de trabajo ni sobre modelos originales. Utilizar pytest, Streamlit AppTest y monkeypatch únicamente para simular fallos; una prueba con mocks no acredita inferencia ni voz reales.

| ID / requisito | Escenario y resultado esperado | Archivo propuesto |
|---|---|---|
| B01 RF04 | load_artifacts real y contrato 2; rechaza copia de artefacto alterada | tests/test_app.py existente |
| B02 RF04 | comparar hashes de src/*.py, config/*.json y artefactos; no aceptar cambios | tests/test_inference.py / test_release.py nuevo |
| B03 RF04 | cohorte keyed regenerada en directorio limpio; verificar manifiesto y particiones 1050/225/225, row_id único y unión 1:1; no asignar por posición | test_release.py |
| C01 RF01 | igualdad ordenada con raw_columns, unicidad, 11 EXT_, 30 clínicos; 20 adicionales según contrato; 56 directos + 7 indicadores = 63 | test_capture.py |
| C02 RF01 | cada campo representado o derivado documentado; no widgets duplicados gingivitis/temblor | test_capture.py / AppTest |
| C03 RF01 | 0,1,null y 7 estados semánticos coherentes; no aplica preservado para derive; ningún valor inicial No | test_capture.py |
| C04 RF01 | vía/tipo parcial: indicador omitido sigue faltante aun si otra vía positiva; No especificado no sustituye null; conservar Otra | test_capture.py |
| C05 RF01 | fecha mensual sin día inventado; edad lactante y duración sin conversión no aprobada; rango fuera de modelo conserva original y advierte | test_capture.py |
| C06 RF01 | frecuencia piscívora > total, fecha inválida, unidad incorrecta; no finalizar inválido; guardar borrador | test_capture.py |
| C07 RF01 | CI/teléfono texto conserva ceros iniciales; no exigirlos al finalizar; fecha notificación requerida por regla operativa | test_capture.py |
| D01 RF02 | crear, cerrar conexión y proceso, reabrir; igualdad de payload, estados, identidad y versión | test_storage.py + M01 |
| D02 RF02 | editar crea nueva versión; snapshot anterior no cambia; no duplicar caso en rerun | test_storage.py |
| D03 RF02 | rollback de identidad, versión, PII y auditoría ante fallo inyectado | test_storage.py |
| D04 RF02 | FK activas por conexión; fallo de versión obsoleta no sobrescribe; parametrización ante comillas y texto SQL | test_storage.py |
| D05 RF02 | JSON estricto sin NaN/Infinity, UTC con zona y fechas clínicas locales; logs sin valores personales | test_storage.py |
| D06 RF02 | fallo de escritura o disco: no afirmar guardado; preservar buffer | test_capture.py |
| N01–N14 RF03 | ejecutar literalmente todos los escenarios de NLP_SPEC, incluida negación coordinada, contraste, pasado, tercero, incertidumbre, conflicto, edad, cefalea y minería | test_nlp.py |
| N15 RF03 | cada alias canónico clínico; offsets Unicode fin exclusivo; coincidencia token completo y solapamientos | test_nlp.py |
| N16 RF03 | allowlist exacta de 34; no PII, ocupación ni dictamen; texto >4000 caracteres sin truncar | test_nlp.py |
| N17 RF03 | aceptar/rechazar individualmente; dato no mencionado intacto; conflicto exige decisión y versión; no escribir desde extractor | test_nlp.py |
| V01 RF06 | WAV local conocido, referencia manual, Vosk real sin red; transcripción editable antes de extraer | test_speech.py + M02 |
| V02 RF06 | modelo ausente, audio inválido, permiso denegado o límite 60 s/5 MiB; texto/manual disponible; no persistir audio | test_speech.py + M02 |
| I01 RF04 | adaptador positivo incluye contexto legítimo de derive, excluye PII, targets, latentes, row_id y laboratorios en snapshot prelab | test_integration.py |
| I02 RF04 | modelo real: salida cinco targets, SHAP de modelos independientes, M3A y aviso experimental; comparar con llamada directa al backend para mismo input | test_integration.py |
| I03 RF04 | añadir/alterar solo laboratorio o PII no cambia vector/predicción M1 para snapshot fijo; no sobreescribir resultado previo | test_integration.py |
| I04 RF04 | categoría inédita se conserva en captura y se proyecta como faltante según transformador congelado; sin fit | test_integration.py |
| I05 RF04 | probable, sospechoso y confirmado según motor existente; confirmación requiere ambos dosajes validados y unidades correctas; aviso de notificación no equivale a envío | tests/test_normative.py + test_integration.py |
| I06 RF04 | sin medición elegible M3B sin puntaje; cero medido no es ausencia; distinguir orina ug/g y ug/g Cr; conflictos de muestras requieren selección | test_integration.py |
| I07 RF04 | motor/artefacto ausente o corrupto: captura y guardado funcionan, inferencia bloqueada; no st.stop global | test_app.py / test_capture.py |
| E01 RF05 | CSV/JSON exportación positiva sin PII, observaciones, firma, targets, latentes ni geografía fina; nulos y metadatos de versión | test_exporter.py |
| E02 RF05 | casos locales separados de cohorte sintética; caracteres Unicode y CSV seguro frente a fórmulas en hojas de cálculo | test_exporter.py |
| T01 RF07 | deduplicar versiones, homónimos separados, coordenadas finitas/rangos/fuente/alcance; faltantes no se convierten en 0,0 | test_territorial.py |
| T02 RF07 | Haversine conocido con tolerancia documentada; DBSCAN dos grupos y ruido, vacío y punto único; determinismo salvo renumeración | test_territorial.py |
| T03 RF07 | conteos vulnerabilidad con desconocidos y OR sin duplicar; demanda sin evaluación o geografía reportada | test_territorial.py |
| T04 RF08 | matriz válida, depósito inicio/fin, capacidad, distancia y tiempo supuesto; verificador independiente de restricciones | test_territorial.py |
| T05 RF08 | capacidad insuficiente, nodo sobredimensionado, solver sin solución, dependencia ausente; no inventar ruta; demanda asignada + no asignada = elegible | test_territorial.py |
| T06 RF08 | estimación ceil con coeficientes explícitos; sin datos no estimar; etiqueta geodésica y ficticia | test_territorial.py |
| U01–U16 | ejecutar todos los criterios UI_SPEC; AppTest para estado, cambio de caso, revisión, guardado, navegación y regresión; manual donde corresponda | test_app.py / test_capture.py + M01–M04 |

## 4. Seguridad y privacidad (solo ficción)
Usar marcadores ficticios únicos para nombre, CI, teléfono, observación y firma; comprobar ausencia en exportación, snapshot de inferencia, log y listado. Verificar que archivos DB, WAL, SHM, backup, audio y QA no se versionen mediante git status y git check-ignore. Sin PII real en fixtures, capturas ni consola. Verificar localhost 127.0.0.1, sin túnel, sin recursos CDN, sin telemetría de Streamlit. SQLite sin cifrado ni autenticación no es apto para datos reales. No confundir pseudonimización y anonimización.

## 5. Ejecución y evidencia
Desde raíz y entorno verificado según DEPLOYMENT.md:
```bash
python -m pip check
python -m pytest -v --junitxml=data/local/qa/pytest.xml
```
Crear carpeta QA previamente. Ejecutar baseline antes de cambios y regresión después; guardar XML separados. Si se modifica navegación, justificar actualización de tests/test_app.py; no eliminar assertions clínicas ni de integridad. Reportar tests passed/failed/skipped/error y motivos; skip de P0 no equivale a aprobado. No imponer cobertura porcentual arbitraria: cobertura de todos los RF P0 y escenarios críticos obligatoria.

M01: desconectar Wi-Fi/Ethernet (mantener loopback), iniciar desde proceso nuevo; crear ficha ficticia, guardar, cerrar servidor, reiniciar, recuperar, editar y exportar. M02: grabar frase de prueba y transcribir con Vosk real; probar negación, edición y fallo de modelo; no conservar voz personal. M03: ejecutar inferencia real, laboratorio y territorio/rutas con datos ficticios; comprobar aviso experimental y restricciones. M04: inspeccionar solicitudes del navegador y conexiones del proceso (herramientas locales del SO); ninguna dependencia externa ni intento de conexión externa de la app durante el flujo. Registrar SO, Python, commit, hash manifiesto, fecha, duración, método y resultado. Desconexión física acredita disponibilidad offline, no por sí sola ausencia de intentos de red.

## 6. Métricas y release
NLP: TP/FP/FN y precision/recall/F1 micro y por campo sobre evaluación separada de desarrollo; sin soporte, no evaluable. Todos los casos críticos N01–N14 deben pasar; cero mutaciones prohibidas. Voz WER y errores clínicos/negaciones; sin umbral clínico inventado. M1 conservar métricas congeladas y paridad de inferencia; no recalibrar en test. Territorio cobertura, ruido, demanda asignada/no asignada, restricciones, distancia geodésica y tiempo cálculo. Medir latencia de arranque, guardado, NLP e inferencia en equipo de demo; reportar observaciones sin SLA no validado.

Acta por prueba: ID, RF, commit, entorno, fixture, esperado, observado, estado PASS/FAIL/SKIP/NOT_RUN, evidencia, incidencia. Release completo solo si G0–G3 y G5 pasan y P1 completados; release parcial demo si P0 pasa y P1 explícitamente faltante; si P0 falla, solo prototipo parcial no aceptado. No certificar normativa ni clínica. Reservar 70 min de ventana propuesta para QA/empaquetado y 20 min reserva/demo; detener ampliaciones si peligra P0.
