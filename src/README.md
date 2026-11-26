# Backend de vigilancia de intoxicación por mercurio en Bolivia

Esta documentación describe el contrato v2 congelado en el commit `87f02da`. El backend separa la clasificación normativa de tres salidas experimentales para triaje, fenotipado y revisión preanalítica. Las métricas se obtuvieron con una cohorte sintética y describen el desempeño dentro de ese simulador.

## 1. Linaje, gobernanza y prevención de fugas

El generador [`generate_synthetic_bolivia.py`](../mercurio_mvp_v4/generate_synthetic_bolivia.py) produce los seis archivos operativos en formato `--keyed`. La fuente asigna un `row_id` único antes de exportar la ficha, `X_M1`, `X_M3A`, `X_M3B`, `Y` y el archivo restringido de auditoría. La ficha operativa conserva los resultados medidos por matriz, mientras que la histórica solo conserva el resultado principal. [`audit_data.py`](audit_data.py) verifica unicidad, igualdad de conjuntos de IDs y paridad de matrices. Alinea las seis fuentes por clave, con independencia del orden físico. La cohorte fija tiene 1.500 registros y semilla 42, con 1.050 en `train`, 225 en `validation` y 225 en `test`. Hay 1.214 registros elegibles para M3B. [Informe de auditoría](../reports/data_audit.json)

- [`PRELAB_ALLOWLIST`](../config/feature_config.json) limita M1 y M3A a señales disponibles antes del laboratorio. Excluye biomarcadores, clase normativa, objetivos, indicadores operativos y el identificador como predictor. Las derivadas se construyen sobre campos prelaboratorio explícitos. M3A también excluye demografía del espacio de agrupamiento.
- [`auditoria_latente_NO_ENTRENAR.csv`](../mercurio_mvp_v4/auditoria_latente_NO_ENTRENAR.csv) aporta exclusivamente la clave, la partición y la bandera de anomalía. La bandera se usa para calibrar y evaluar M3B una vez ajustado el bosque. Las columnas latentes quedan fuera de las matrices predictoras y del ajuste de transformadores.
- Un cero observado denota ausencia para un indicador clínico. `NaN` conserva el estado desconocido o sin medición. M1 usa el tratamiento nativo de faltantes de LightGBM y excluye cada etiqueta cuando falta el biomarcador correspondiente. M3A calcula distancias con observaciones compartidas. M3B aplica una imputación interna por medianas del subconjunto elegible de `train`, con cero como recurso si la columna carece de mediana. Esa imputación sirve solo para puntuar con el bosque, sin crear una medición clínica.
- [`transform_record()`](features_pipeline.py) usa la misma proyección y los mismos artefactos en entrenamiento e inferencia. Vocabularios, percentiles, escalas y estadísticas de imputación se ajustan en `train` y se serializan en `transformers.joblib`. La proyección sin artefactos sirve para verificar la paridad con los CSV de referencia.

## 2. Capa 1 — Motor normativo determinístico

| Fuente en la Guía Técnica N.º 537 (2024) | Regla aplicada |
|---|---|
| §15.2, p. 36 | **Probable** requiere antecedente de exposición confirmada o procedencia de una zona de riesgo, más una manifestación aguda o crónica evaluada como compatible. **Confirmado** requiere además dosajes validados elevados en sangre y orina. |
| §15.2, p. 36, y Cuadro 3, p. 32 | Para automatizar la confirmación se adoptó el extremo superior del intervalo sanguíneo, **>20 µg/L**, y **>50 µg/g** en orina. Ambos cortes son estrictos y requieren validación del resultado. |
| Cuadro 3, p. 32 | Referencias registradas por matriz: cabello 3 µg/g (FAO/OPS) y 1 µg/g (EPA), sangre <10–20 µg/L (OMS), orina <50 µg/g (OMS), cordón <5,8 µg/L (EPA). |
| §9 y Cuadro 1, pp. 28–30 | La tríada de eretismo, temblor y gingivitis se registra como evidencia clínica cuando está documentada. El criterio de compatibilidad se captura mediante evaluación clínica. |
| §6.1, pp. 24–25, y Cuadro 2, p. 32 | Prioridad para mujeres en edad fértil, embarazadas y exposición fetal, niñas, niños y adolescentes, y exposición crónica sistemática. Lactancia se registra por separado. El rango de 15–49 años es operativo del MVP. |

`Sospechoso` es un estado operativo para exposición con evaluación clínica pendiente. La sección 15.2 enumera dos estados oficiales, Probable y Confirmado. Para confirmar, el servicio requiere el criterio clínico registrado, los dosajes con sus unidades y los indicadores `laboratorio_sangre_validado` y `laboratorio_orina_validado`. Una medición de cordón no satisface el requisito de sangre. La orina en µg/g y en µg/g de creatinina representan magnitudes distintas. El objetivo histórico de M1 usa µg/g de creatinina, mientras que la confirmación normativa usa µg/g. Ninguna salida predictiva interviene en la clasificación del caso. La capa también devuelve validación de la ficha, ingesta diaria estimada, vulnerabilidad y orientación de biomarcador. [Reglas y referencias](../config/normative_rules.json) · [Motor normativo](normative_engine.py)

## 3. Ingeniería de características y evaluación

### M1 — Triaje mediante LightGBM y SHAP

El espacio de triaje combina exposición, susceptibilidad, clínica prelaboratorio, carga dietética y ocupacional, intervalos y recencia toxicocinética, y completitud. La recencia usa $2^{-t/h}$ con semividas operativas de 3,8, 30, 50 y 90 días. Las fechas parciales permiten conservar cotas. La selección por promedio de precisión en validación cruzada dentro de `train` compara síntomas crudos, índices sindrómicos y una representación híbrida para cada objetivo. La auditoría de representación registra linaje, correlación de Spearman, V de Cramér corregida, VIF y agrupamiento jerárquico. [Derivadas](derived_features.py) · [Auditoría de representación](../reports/representation_m1.json)

Los objetivos se estratifican en cabello a 1, 3 y 5 µg/g, y orina a 20 y 50 µg/g de creatinina. EPA usa la medición observada y los cuatro objetivos históricos conservan la etiqueta sintética en el subconjunto medido. El objetivo de cordón se registra como sin modelo porque la cohorte carece de mediciones. El ajuste usa parada temprana y la calibración se realiza en validación con sensibilidad mínima de 0,90, elevada a 1,00 para el objetivo urinario Guía 537.

En cada cadena se acota la probabilidad publicada del corte mayor por la del corte menor. Los umbrales de alerta se ordenan en sentido compatible con esa cadena. El resultado tiene cero inversiones en las salidas publicadas. El informe conserva también las inversiones de los modelos independientes. SHAP explica los modelos independientes en log-odds, con seis contribuciones por registro y sumas por dominio. [Código M1](model_m1.py) · [Auditoría de monotonía](../reports/monotonicity_m1.json)

La PR-AUC se calcula como *Average Precision*. Cada métrica se presenta en escala de 0 a 1.

| Objetivo | Partición | Sensibilidad | Especificidad | PR-AUC | Balanced Accuracy | Brier |
|---|---|---:|---:|---:|---:|---:|
| `y_mehg_cabello_bolivia` | val | 1,000 | 0,109 | 0,675 | 0,555 | 0,197 |
| `y_mehg_cabello_bolivia` | test | 0,963 | 0,267 | 0,732 | 0,615 | 0,127 |
| `y_mehg_cabello_5` | val | 0,913 | 0,279 | 0,516 | 0,596 | 0,163 |
| `y_mehg_cabello_5` | test | 0,944 | 0,435 | 0,607 | 0,690 | 0,115 |
| `y_hg_urinario_hbm2` | val | 0,938 | 0,648 | 0,600 | 0,793 | 0,093 |
| `y_hg_urinario_hbm2` | test | 0,812 | 0,574 | 0,393 | 0,693 | 0,110 |
| `y_hg_urinario_guia537` | val | 1,000 | 0,806 | 0,173 | 0,903 | 0,042 |
| `y_hg_urinario_guia537` | test | 0,727 | 0,778 | 0,322 | 0,753 | 0,081 |
| `y_mehg_cabello_epa` | val | 1,000 | 0,000 | 0,911 | 0,500 | 0,145 |
| `y_mehg_cabello_epa` | test | 1,000 | 0,000 | 0,928 | 0,500 | 0,160 |

El objetivo urinario Guía 537 tuvo 11 positivos entre 110 registros evaluables de prueba. Detectó ocho y cada positivo equivale a 9,1 puntos porcentuales de sensibilidad. El 72,7 % observado muestra que la sensibilidad de validación no se reprodujo en prueba. El 75 % histórico se estimó en otro conjunto evaluable. EPA conserva sensibilidad alta con especificidad cero a su umbral operativo en ambos conjuntos. [Métricas y denominadores de prueba](../reports/metrics_m1.csv) · [Métricas de validación](../models/manifest.json)

### M3A — Fenotipado mediante Gower y HDBSCAN

La representación publicada FEN-B usa Gower con pesos de **0,55 clínica**, **0,30 exposición** y **0,15 temporalidad**. Las variables continuas asimétricas se escalan con logaritmo y los percentiles 5 y 95 de `train`. La cobertura compartida mínima es 0,50. HDBSCAN aprende los perfiles en `train` con distancias precalculadas. En inferencia, se asigna el medoide más cercano si la distancia es finita y no supera el radio $P_{90}$ intraclúster. El código `-1` señala ruido o cobertura insuficiente.

Los cuatro perfiles aprendidos reciben asignaciones en ambos conjuntos. Se asignaron **105/225** registros en validación y **106/225** en prueba. La cobertura de asignación fue similar entre particiones. Esa comparación mide transferencia de los perfiles congelados a registros reservados, sin cuantificar su estabilidad bajo remuestreo. El informe conserva conteos por perfil, radios, un comparador FEN-A y resúmenes de biomarcadores externos por grupo. [Código M3A](model_m3a.py) · [Métricas M3A](../reports/metrics_m3a.json)

### M3B — Revisión preanalítica mediante Isolation Forest

El bosque se ajusta solo en 850 registros de `train` con al menos una medición elegible. Cada biomarcador se representa con $Z_m=\ln(B_m/u_m)$, donde $u_m$ es una unidad de la escala registrada. Antes del logaritmo se aplica un piso de 0,005 en esa escala. Se resta la mediana del logaritmo condicionada al grupo de exposición y se divide por una escala robusta $\mathrm{IQR}/1{,}349$. Ambas estadísticas provienen de `train`, con respaldo global por matriz. El bosque también utiliza longitud del segmento capilar y demora de envío.

| Señal de discordancia | Construcción |
|---|---|
| `ratio_hg_cabello_vs_exposicion_dietetica` | Mercurio capilar dividido por uno más la frecuencia de consumo de peces piscívoros. |
| `ratio_hg_orina_vs_exposicion_inhalatoria` | Mercurio urinario dividido por uno más diez veces el eje inhalatorio-ocupacional. |
| `indice_discordancia_asintomatico_extremo` | Exceso sobre referencias operativas internas, ponderado por ausencia de síntomas cuando la completitud llega a 0,70 y el índice sindrómico es como máximo 0,10. |
| `flag_incoherencia_matriz_via` | Señala cabello como única medición ante exposición inhalatoria sin consumo piscívoro, u orina como única medición ante consumo piscívoro sin exposición inhalatoria. |

| Partición elegible | Sensibilidad | Precisión | Especificidad | PR-AUC |
|---|---:|---:|---:|---:|
| Validación (187) | 90,5 % (19/21) | 36,5 % | 80,1 % | 0,782 |
| Prueba (177) | 81,8 % (9/11) | 25,7 % | 84,3 % | 0,682 |

La detección pasó de **1/11 (9,1 %)** a **9/11 (81,8 %)** en prueba frente a `flag_anomalia_real`, la referencia de anomalías inyectadas por el simulador. En prueba hubo 35 alertas, 26 de ellas falsos positivos. El umbral se eligió en validación con la etiqueta externa, una vez ajustado el bosque. La alerta orienta una revisión de laboratorio. [Código M3B](model_m3b.py) · [Métricas M3B](../reports/metrics_m3b.json)

## 4. Serialización, integridad y operación

El [manifiesto](../models/manifest.json) registra `contract_version`, semilla, Python, versiones de dependencias, métricas y cuatro mapas SHA-256: `data_sha256`, `source_sha256`, `config_sha256` y `artifact_sha256`. El cargador valida el contrato, los hashes del código Python bajo `src/`, los JSON de configuración y los archivos de modelo y umbrales listados. Las huellas de datos permiten rastrear los archivos usados en el ajuste. Los hashes verifican consistencia contra el manifiesto. La procedencia confiable de los archivos `.joblib` y del manifiesto debe establecerse antes de cargarlos.

[`load_artifacts()`](inference.py) prepara transformadores, modelos, umbrales, medoides y explicadores SHAP. `predict_patient(record_dict, artifacts)` devuelve `normativo`, `m1`, `m3a`, `m3b` y `aviso_experimental`. Cuando falta laboratorio elegible, M3B devuelve `elegible: false` y deja puntaje y alerta sin valor. La futura interfaz puede reutilizar el cargador y llamar a inferencia para cada ficha.

Desde la raíz del repositorio, con Python 3.12:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python src/audit_data.py
python src/train_models.py
pytest -v
```

`audit_data.py` prepara `data/` si todavía no existe el conjunto de entrada y escribe el informe de auditoría. `train_models.py` vuelve a auditar, reentrena y escribe los artefactos y reportes. Para consumir el cierre publicado se cargan directamente los artefactos del commit. La suite de **11 pruebas unitarias y de integración** cubre reglas, unidades y estados normativos, paridad y alineación por ID, derivadas y faltantes, cobertura de Gower, monotonía e inferencia con y sin laboratorio.

```python
from src.inference import load_artifacts, predict_patient

artifacts = load_artifacts("models")
result = predict_patient({"edad": 38, "antecedente_exposicion_hg": True}, artifacts)
```
