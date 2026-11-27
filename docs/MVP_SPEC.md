# MVP — Especificación maestra de ingeniería

Estado: candidato para implementación; no validado en ejecución. Base: commit `56408ec57c98006cfc37df4e3fa3d5ce10867927`, contrato backend v2. Guía Técnica 537 (2024), pp. 17, 20–39, especialmente 32, 34, 36–38, según definiciones previamente acordadas. La trazabilidad ítem por ítem queda pendiente de cotejo con la ficha original.

## Objetivo y alcance
Capturar fichas de vigilancia de mercurio sin Internet en una computadora local; asistir la captura con texto y voz; persistir registros; reutilizar inferencia normativa, M1, M3A y M3B; proporcionar planificación territorial demostrativa. No es un dispositivo clínico validado. Solo datos ficticios en hackatón. No publicar datos, abrir puertos públicos ni desplegar remotamente sin aprobación.

## Fuentes y precedencia
1. Guía 537 para definiciones oficiales; ambigüedades requieren revisión profesional.
2. `config/schema.json`, `config/feature_config.json`, `config/normative_rules.json`, código de `src/` y `models/manifest.json` para contrato computacional congelado.
3. `app/capture_schema.json` y `docs/DATA_CONTRACT.md` para nuevas decisiones de captura. Si discrepan con el backend, detener la integración de ese campo y documentar; no cambiar el modelo silenciosamente.

## Arquitectura y límites de modificación
Python 3.12 según `app/README.md`; Streamlit local (127.0.0.1), SQLite, spaCy `blank('es')` con reglas; Vosk local para voz; DBSCAN Haversine y OR-Tools para demostración territorial. M1 LightGBM+SHAP, M3A Gower/HDBSCAN y M3B Isolation Forest siguen siendo módulos existentes. Usar nombres M2_TERRITORIO y M3_NLP para nuevos módulos. No entrenar en interfaz.

`load_artifacts()` verifica todos los JSON de `config/` y PY de `src/`, además de artefactos. No añadir ni modificar archivos allí ni cambiar manifiesto o modelos. Implementar bajo `app/`, pruebas bajo `tests/`, documentación bajo `docs/`; dependencias adicionales aisladas y compatibles. No eludir comprobaciones. Usar `predict_patient()` y `validate_record()` existentes mediante adaptador explícito. Captura y guardado deben funcionar aunque el motor predictivo falle.

## Requerimientos y aceptación
| ID | Prioridad | Función | Prueba de aceptación |
|---|---|---|---|
| RF01 | P0 | Captura completa de 82 columnas y campos operativos aplicables | Cada identificador del esquema aparece una vez, editable o derivado documentado; borradores admiten ausencia |
| RF02 | P0 | SQLite persistente | Crear, cerrar proceso, reiniciar, recuperar y editar con versión incremental |
| RF03 | P0 | NLP textual local | Propuestas con evidencia, negación, incertidumbre y sujeto; no sobreescribir sin aceptación |
| RF04 | P0 | Triaje existente | Carga SHA-256 íntegra, M1 y M3A; M3B sin puntuación sin laboratorio elegible |
| RF05 | P0 | Exportación analítica | Sin PII ni etiquetas latentes; nulos preservados; CSV/JSON local |
| RF06 | P1 | Voz local | Audio breve -> transcripción editable -> mismo NLP sin red; fallo no bloquea captura |
| RF07 | P1 | Territorio | DBSCAN con datos ficticios, conserva puntos aislados; faltantes excluidos con conteo |
| RF08 | P1 | Rutas | OR-Tools con matriz de distancia local y capacidad; informa inviabilidad; rutas no viales etiquetadas |
| RF09 | P2 | Sincronización institucional | Fuera del alcance; exportación manual no equivale a notificación oficial |

P1 es objetivo de demostración, no autorización para sacrificar P0. Si hay bloqueo, entregar funcionalidad parcial etiquetada, nunca simular que se ejecutó.

## Reglas clínicas y epidemiológicas
Caso probable: exposición confirmada o procedencia de zona de riesgo más manifestación compatible evaluada profesionalmente. Confirmado: caso probable con dosajes que superen referencias en sangre y orina conforme a guía; el backend adopta sangre >20 µg/L y orina >50 µg/g con validaciones explícitas. Es una interpretación operativa que requiere verificación clínica de referencias y unidades. No equiparar orina por masa con orina ajustada a creatinina. Sospechoso es estado operativo. La regla de notificación inmediata de probable (p.38) debe mostrarse como aviso; exportar no acredita notificación. NLP no establece dictamen, confirmación, prioridad definitiva ni exposición confirmada por inferencia. Señales graves requieren revisión profesional independiente de puntuación. Rangos 15–49 y menor de 18 son operativos, no límites oficiales de la guía. Resultados de modelos sintéticos no son probabilidades clínicas validadas; SHAP explica modelos independientes, no causalidad.

## Plan de seis horas (presupuesto propuesto)
| Minutos | Hito | Puerta |
|---|---|---|
| 0–30 | Verificar entorno, manifiesto, pruebas; cerrar contrato | Evidencia de carga o bloqueo explícito |
| 30–105 | Captura y SQLite | Guardado/recuperación y paridad de esquema |
| 105–165 | NLP y unión con formulario | Casos de negación y conflicto aprobados |
| 165–195 | Voz local | Prueba sin red o degradación explícita a texto |
| 195–240 | Territorio y rutas | Datos ficticios y restricciones verificadas |
| 240–270 | Integración inferencia y exportación | Flujo de punta a punta |
| 270–340 | Regresión, prueba offline y empaquetado | Informe de pruebas, limitaciones |
| 340–360 | Reserva y demostración | Arranque reproducible |

Paralelizar NLP y territorio tras contrato aprobado si existen sesiones separadas; solo integrador modifica `app/app.py`. No publicar ni hacer push sin autorización explícita.

## Verificación inicial
Desde raíz, entorno Python 3.12. Instalar `requirements-dev.txt` y verificar versiones del manifiesto. Ejecutar `python mercurio_mvp_v4/generate_synthetic_bolivia.py --keyed --out data` exclusivamente sobre directorio limpio y sin datos de usuario; si existe, usar copia de trabajo. Comparar SHA-256 con manifiesto, ejecutar `python -m pytest -v`, y `streamlit run app/app.py --server.address 127.0.0.1`. Si hashes difieren, no sustituir los esperados; conservar captura manual y reportar bloqueo. La cohorte original versionada no es la generación keyed usada por backend. No anexar row_id por posición.

## Definition of Done
Entregar cambios revisables, pruebas nuevas y anteriores con resultados reales, instrucciones de inicio, inventario de dependencias y modelos locales, evidencia de funcionamiento sin red, lista de fallos y decisiones no resueltas. No declarar validación clínica, certificación normativa ni despliegue por mera generación de código.
