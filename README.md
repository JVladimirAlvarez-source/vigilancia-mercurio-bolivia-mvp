# Vigilancia Inteligente de Intoxicación por Mercurio — Bolivia (MVP)

Sistema de soporte a la decisión clínica, fenotipado computacional y auditoría preanalítica alineado con la **Guía Técnica N.º 537 (Ministerio de Salud y Deportes de Bolivia, 2024)**.

> **Propósito de este documento:** Este `README.md` funciona simultáneamente como **documentación científica** y como **contrato de ingeniería de contexto** para colaboradores. Define la arquitectura exacta de separación de datos, las ecuaciones de *Feature Engineering* y los guardarraíles contra *data leakage* necesarios para entrenar, auditar y desplegar el sistema sin percances.

---

## 1. Arquitectura de Datos y Separación Física Anti-Leakage

La arquitectura opera exclusivamente sobre fichas epidemiológicas y resultados de laboratorio (sin variables geoespaciales ni logísticas), diferenciando tres conceptos clínicos: **Exposición** (contacto con fuente), **Carga biológica** (biomarcador) e **Intoxicación clínica** (diagnóstico médico).

Para evitar fuga de información (*data leakage*) y contaminación del proceso asistencial, el pipeline implementa listas explícitas de variables permitidas (`PRELAB_ALLOWLIST`) y separa físicamente los datos en tres espacios independientes:

| Espacio | Algoritmo | Entradas Permitidas | Prohibiciones Estrictas | Finalidad |
| :--- | :--- | :--- | :--- | :--- |
| **$X_{\text{M1}}$** | `LightGBM + SHAP` | Ficha clínica pre-laboratorio (demografía, síntomas, exposición, temporalidad) | `lab_*`, `EXT_67b*`, `y_*`, variables latentes e `indicador_laboratorio_pendiente` | Triaje predictivo de riesgo por matriz y especie química |
| **$X_{\text{M3A}}$** | `Gower + HDBSCAN` | Síntomas, ejes clínicos, exposición y temporalidad pre-laboratorio | Biomarcadores, predicciones de `M1`, etiquetas diagnósticas y demografía en clustering base | Descubrimiento no supervisado de fenotipos clínicos |
| **$X_{\text{M3B}}$** | `Isolation Forest` | Ficha pre-laboratorio + biomarcadores medidos + metadatos preanalíticos | Variables latentes de auditoría (`flag_anomalia_real`) y particiones `val`/`test` durante ajuste | Auditoría de discordancias clínico-toxicológicas y contaminación |

---

## 2. Contrato de Ingeniería de Características (*Feature Engineering*)

Las decisiones etiquetadas como **`[PE]`** (*Propuesta Experimental sin Validación Local*) son hipótesis de ingeniería respaldadas por literatura toxicológica/estadística que requieren calibración con datos reales del SEDES/SNIS.

### 2.1. Rama M1 — Triaje Clínico y Toxicocinético (`LightGBM + SHAP`)

#### A. Separación por Especie Química y Vulnerabilidad Materno-Infantil
No se construye un índice único de exposición: se separan **mercurio elemental** ($\text{Hg}^0$, inhalación en quema de amalgama $\rightarrow$ SNC/riñón/pulmón $\rightarrow$ orina/sangre), **mercurio inorgánico** ($\text{Hg}^{2+}$ $\rightarrow$ riñón/TGI $\rightarrow$ orina) y **metilmercurio** ($\text{MeHg}$, consumo de pescado $\rightarrow$ SNC/neurodesarrollo fetal $\rightarrow$ cabello/sangre/cordón) (Clarkson & Magos, 2006, DOI: `10.1080/10408440600845619`).

* **Interacciones de susceptibilidad:** `embarazo_x_consumo_piscivoros`, `embarazo_x_quema_amalgama`, `edad_fertil_x_quema_amalgama`, `lactancia_x_carga_ictica` (Maurice-Bourgoin et al., 2000, PMID: `11032117`; Stern & Smith, 2003, DOI: `10.1289/ehp.6187`), `nino_x_consumo_pescado` (Benefice et al., 2008, DOI: `10.1080/09603120802272235`), `exposicion_mixta` (Barbieri et al., 2009) y `exposicion_riberenia` (Monrroy et al., 2008, PMID: `19004394`).
* **Regla clínica:** Embarazo, lactancia y edad pediátrica elevan la **prioridad sanitaria normativa** (Capa 1), sin asumir artificialmente mayor concentración biológica.

#### B. Índices Sindrómicos Normalizados ($I_s$)
Agrupan los 30 síntomas de la ficha en 10 dominios (`neurologico_motor`, `neurologico_sensorial`, `eretismo`, `cognitivo`, `oral`, `renal_clinico`, `cutaneo`, `respiratorio_agudo`, `gastrointestinal`, `sintomas_inespecificos`):

$$I_s = \frac{\sum_{i \in O_s} w_i x_i}{\sum_{i \in O_s} w_i} \in [0, 1]$$

Donde $O_s$ es el conjunto de síntomas **efectivamente evaluados** ($w_i = 3$ para signos cardinales como temblor, ataxia, parestesias o eretismo; $w_i = 2$ para estomatitis/gingivitis/memoria; $w_i = 1$ para síntomas inespecíficos como cefalea o náuseas `[PE]`). Si $O_s = \emptyset$, $I_s = \text{NaN}$. Incluye interacciones `interaccion_neuro_dieta` (PMID: `20851675`) e `interaccion_eretismo_ocupacional`.

#### C. Carga Dietética ($IC_{30}$, $EDI$) y Exposición Ocupacional ($TEP$)
Calibrado con datos del río Beni (Loayza et al., 2026, DOI: `10.1016/j.jfca.2025.108840`: *mota* $1{,}9 \pm 1{,}0\ \mu\text{g/g}$; *pacú* y *paiche* $< 0{,}5\ \mu\text{g/g}$):

$$IC_{30} = \sum_{s=1}^{n} F_{s,30} \cdot P_s \cdot C_s \cdot q_s \qquad \text{y} \qquad EDI = \frac{IC_{30}}{30 \cdot PC}\quad (\mu\text{g MeHg/kg/día})$$

* **Exposición laboral:** `tiempo_exposicion_laboral_horas`, `horas_quema_amalgama`, `quema_en_espacio_cerrado`, `exposicion_domestica_indirecta` y `tiempo_exposicion_ponderado` ($TEP = \sum H_a W_a$ `[PE]`).

#### D. Ingeniería Temporal y Recencia Toxicocinética Multifásica
Dado que la eliminación del mercurio es multifásica y depende de la especie química (OMS, 2024; ATSDR, 2024), se calculan intervalos (`retardo_consulta_dias`, `dias_desde_ultima_exposicion`, `duracion_sintomas_dias`, `duracion_exposicion_dias`, `latencia_sintomatica_dias`, `exposicion_continua`, `flag_incoherencia_temporal`) y coeficientes adimensionales de recencia tras el cese de exposición:

$$K(t; h) = \exp\left(-\frac{\ln 2}{h} t\right) = 2^{-t/h}, \qquad h \in \{3{,}8\text{ d (fase rápida sangre)},\ 30\text{ d},\ 50\text{ d (MeHg)},\ 90\text{ d (Hg}^0\text{ tisular)}\}$$

Para fechas imprecisas (solo mes conocido), se conservan cotas $[K_{\min}, K_{\max}] = [2^{-t_{\max}/h}, 2^{-t_{\min}/h}]$.

#### E. Patrones de Faltantes Informativos (*Missingness Features*) e Incertidumbre Clínica
En vigilancia rural, `No` ($0$) es distinto de `Desconoce / No evaluado` ($\text{NaN}$, máscara de observación $R_j = 0$, aplicabilidad $A_j = 1$) y de `No aplica` ($A_j = 0$) (Rubin, 1976; Che et al., 2018, DOI: `10.1038/s41598-018-24271-9`; Agniel et al., 2018):

* **Variables de completitud:** `proporcion_sintomas_evaluados` ($C_{\text{clin}} = \sum A_j R_j / \sum A_j$), `conteo_sintomas_presentes`, `conteo_sintomas_no_evaluados`, `proporcion_sintomas_positivos`, `conteo_desconoce_exposicion`, `proporcion_exposicion_evaluada`, `missingness_sindromico_s` y `flag_informacion_contradictoria`.
* **Cotas de incertidumbre clínica `[PE]`:**

$$I_{\min} = \frac{n_{\text{positivos}}}{n_{\text{aplicables}}}, \qquad I_{\max} = \frac{n_{\text{positivos}} + n_{\text{desconocidos}}}{n_{\text{aplicables}}}, \qquad U = I_{\max} - I_{\min}$$

#### F. Control de Multicolinealidad y Explicabilidad SHAP
* **Protocolo:** Eliminar varianza cero $\rightarrow$ grafo de linaje de features $\rightarrow$ Spearman ($\vert{}\rho_s\vert{} \ge 0{,}85$) y Cramér's V corregido ($\ge 0{,}80$, Bergsma, 2013) $\rightarrow$ VIF auxiliar ($\ge 5$) $\rightarrow$ clustering jerárquico de enlace completo ($1 - \vert{}\rho_s\vert{}$) $\rightarrow$ validación cruzada antes de congelar la representación (`M1-A` síntomas crudos vs. `M1-B` índices vs. `M1-C` híbrido).
* **Agregación SHAP:** Para grupos clínicos disjuntos $G_s$, $\Phi_{G_s}(x) = \sum_{j \in G_s} \phi_j(x)$ (Lundberg et al., 2020, DOI: `10.1038/s42256-019-0138-9`).

#### G. Targets Estratificados ($Y$)
Nunca se entrenan targets mezclando `NaN == 0` (si falta biomarcador válido, $Y = \text{NaN}$):
* `y_mehg_cabello_epa` ($\ge 1\ \mu\text{g/g}$), `y_mehg_cabello_bolivia` ($\ge 3\ \mu\text{g/g}$, Guía 537), `y_mehg_cabello_5` ($> 5\ \mu\text{g/g}$, PMID: `20851675`).
* `y_hg_urinario_hbm2` ($\ge 20\ \mu\text{g/g Cr}$, OMS 2008 / ACGIH BEI), `y_hg_urinario_guia537` ($\ge 50\ \mu\text{g/g Cr}$, Guía 537).
* `y_hg_cordon` ($\ge 5{,}8\ \mu\text{g/L}$, Guía 537 / EPA).

---

### 2.2. Rama M3A — Fenotipado Clínico No Supervisado (`Gower + HDBSCAN`)

#### A. Ejes Fisiopatológicos y Proyecciones Compuestas (`[PE]`)
* **10 ejes clínicos:** `eje_neuromotor`, `eje_sensorial`, `eje_neuropatia_periferica`, `eje_neuropsiquiatrico`, `eje_oral_inorganico`, `eje_respiratorio_inhalatorio`, `eje_renal`, `eje_cutaneo`, `eje_gastrointestinal`, `eje_ocular` + `flag_convulsiones` y `flag_hepatomegalia`.
* **7 ejes de exposición/temporalidad:** `eje_inhalatorio_ocupacional`, `eje_dietetico`, `eje_cronicidad`, `eje_recencia_inhalatoria`, `eje_recencia_dietetica`, `eje_exposicion_mixta` ($\min$) y `contraste_exposicion` (diferencia).
* **Proyecciones orientadoras (para interpretación y comparación `FEN-A` clínico vs. `FEN-B` clínico-expositivo):**

$$P_{\text{Hg}^0} = \frac{I_{\text{neuropsiq}} + I_{\text{oral}} + I_{\text{resp}} + I_{\text{renal}}}{4}, \qquad P_{\text{MeHg}} = \frac{I_{\text{sensorial}} + I_{\text{neuromotor}}}{2}$$

$$D_{\text{clin}} = P_{\text{Hg}^0} - P_{\text{MeHg}}, \qquad M_{\text{clin}} = \min(P_{\text{Hg}^0}, P_{\text{MeHg}})$$

#### B. Preprocesamiento Mixto, Distancia de Gower Ponderada e Inferencia por Medoides
1. **Escalado robusto acotado (ajustado solo en `train`):** Para variables continuas asimétricas (duración, horas), $u_j = \ln(1 + x_j)$ y $z_j = \text{clip}\left(\frac{u_j - Q_{0{,}05,j}}{Q_{0{,}95,j} - Q_{0{,}05,j}},\ 0,\ 1\right)$.
2. **Distancia de Gower por bloques (Gower, 1971, DOI: `10.2307/2528823`):**

$$D_{il} = \frac{\sum_{b=1}^{B} W_b \, a_{ilb} \, D_{il}^{(b)}}{\sum_{b=1}^{B} W_b \, a_{ilb}}, \qquad W = \{\text{Clínica}: 0{,}55,\ \text{Exposición}: 0{,}30,\ \text{Temporalidad}: 0{,}15\}$$

Exige cobertura compartida mínima $C_{il} = \frac{\sum_j w_j \delta_{ilj}}{\sum_j w_j} \ge 0{,}50$ (comparación admitida $\ge 0{,}70$).
3. **Clustering y asignación en producción:** `HDBSCAN(metric="precomputed", min_cluster_size=20, min_samples=5, cluster_selection_method="eom")` (Campello et al., 2013). Como `approximate_predict()` no soporta matrices precomputadas, el entrenamiento extrae el **medoide** y el **radio $P_{90}$** de cada clúster para asignar nuevos pacientes por mínima distancia de Gower (o marcar como `Atípico / Ruido (-1)` si excede el radio).

---

### 2.3. Rama M3B — Auditoría Preanalítica y Discordancias (`Isolation Forest`)

Opera **únicamente sobre registros con laboratorio disponible dentro de `train`** para detectar contaminación externa de muestras (ej. vapores de $\text{Hg}^0$ adsorbidos en cabello en ambiente minero; Koenigsmark et al., 2021; Suárez-Criado et al., 2023), incoherencia matriz-vía o errores de transcripción/unidades ($\mu\text{g/L}$ vs. $\text{mg/L}$):

1. **Normalización logarítmica de biomarcadores:** $Z_m = \ln(B_m / u_m)$ para evitar confundir intoxicaciones severas reales con errores técnicos.
2. **Residuales clínico-toxicológicos:** Diferencia estandarizada entre el biomarcador observado $Z_m$ y la mediana condicional esperada dada la exposición declarada en `train`.
3. **Ratios de discordancia explícitos:**
   * `ratio_hg_cabello_vs_exposicion_dietetica`: cabello elevado sin consumo relevante de pescado piscívoro (alerta de contaminación externa por $\text{Hg}^0$ o error de unidad).
   * `ratio_hg_orina_vs_exposicion_inhalatoria`: mercurio urinario elevado sin exposición ocupacional ni inorgánica declarada.
   * `indice_discordancia_asintomatico_extremo`: biomarcador por encima de umbrales severos con $I_{\text{clin}} \approx 0$ y completitud clínica alta ($C_{\text{clin}} \ge 0{,}70$).
   * `flag_incoherencia_matriz_via`: matriz analizada incompatible con la vía única declarada.

---

## 3. Reglas de Implementación y colaboracion

1. **Unión por ID y particiones fijas:** Cruza `ficha_mercurio_bolivia_v2.csv`, `X_M1.csv`, `X_M3A.csv`, `X_M3B.csv`, `Y.csv` y `auditoria_latente_NO_ENTRENAR.csv` exclusivamente por `ID` único (`N = 1,500`; `1,050 train / 225 val / 225 test`, `seed = 42`). Nunca uses columnas de `auditoria_latente_NO_ENTRENAR.csv` como features.
2. **Cero *Training-Serving Skew*:** Todo preprocesamiento (cuantiles $Q_{0{,}05}/Q_{0{,}95}$, medianas condicionales de `M3B`, codificadores) debe ajustarse **solo en `train`**, serializarse en `models/` y aplicarse mediante `transform_record()` en `src/features_pipeline.py`.
3. **Evaluación bajo desbalance (`M1` y `M3B`):** Prioriza **PR-AUC (Average Precision)**, **Sensibilidad ($\ge 0{,}90$ en validación)**, **Especificidad**, **Balanced Accuracy** y **Brier Score**.
4. **Calibración obligatoria de `M3B`:** Asegura que `X_M3B` incluya los ratios de discordancia y residuales condicionales de la Sección 2.3 antes de entrenar `IsolationForest`, evaluando recall y precisión contra `flag_anomalia_real` en `test`.
5. **Desacoplamiento de Streamlit (`app/app.py`):** La interfaz web debe usar `@st.cache_resource` para cargar los artefactos congelados en `models/`. **Nunca** ejecutes entrenamiento dentro de `app/app.py`.

---

## 4. Estructura del Repositorio y Ejecución

```text
vigilancia_mercurio_bolivia/
├── app/app.py                          # Interfaz clínica Streamlit (solo inferencia)
├── config/                             # Esquemas, allowlists y reglas Guía N.º 537
├── data/                               # Dataset sintético v2, matrices X/Y y validación
├── models/                             # Artefactos congelados (.joblib) y manifest.json
├── reports/                            # Auditoría de datos y métricas (M1, M3A, M3B)
├── src/
│   ├── generate_synthetic_bolivia.py   # Generador causal SCM v4.0 (seed=42)
│   ├── audit_data.py                   # Auditoría de integridad y anti-leakage
│   ├── normative_engine.py             # Capa 1: Motor determinístico Guía N.º 537
│   ├── features_pipeline.py            # Transformadores M1, M3A y M3B sin leakage
│   ├── model_m1.py                     # Capa 2: LightGBM + SHAP
│   ├── model_m3a.py                    # Capa 3A: Gower por bloques + HDBSCAN + medoides
│   ├── model_m3b.py                    # Capa 3B: Isolation Forest preanalítico
│   ├── train_models.py                 # Orquestador reproducible de entrenamiento
│   └── inference.py                    # Servicio unificado predict_patient()
└── tests/     
```


```powershell
# Ejecución completa en Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/audit_data.py
python src/train_models.py
pytest -v
streamlit run app/app.py

```

---

# 5. Referencias Científicas y Normativas

Ministerio de Salud y Deportes de Bolivia (2024). Guía Técnica N.º 537: Vigilancia Epidemiológica y Atención Integral de la Intoxicación por Mercurio (R.M. 0142).

Clarkson, T. W., & Magos, L. (2006). The toxicology of mercury and its chemical compounds. Critical Reviews in Toxicology, 36(8), 609–662. https://doi.org/10.1080/10408440600845619

ATSDR (2024). Toxicological Profile for Mercury. U.S. DHHS. https://www.atsdr.cdc.gov/toxprofiles/tp46.pdf

OMS / PNUMA (2008). Guidance for Identifying Populations at Risk from Mercury Exposure. Geneva: WHO.

Loayza, E., Peñarrieta, J. M., Achá, D., & Miranda-Chumacero, G. (2026). Balancing nutrients and mercury: Nutritional composition and total mercury content in fish consumed in the Bolivian Amazon (Beni River). Journal of Food Composition and Analysis, 150, 108840. https://doi.org/10.1016/j.jfca.2025.108840

Benefice, E., Luna-Monrroy, S., & Lopez-Rodriguez, R. (2008 / 2010). Fishing activity, health characteristics and mercury exposure of Amerindian women living along the Beni River. IJHEH. PMID: 19004394 / 20851675.

Maurice-Bourgoin, L., et al. (2000). Mercury distribution in waters and fishes of the upper Madeira rivers and mercury exposure in riparian Amazonian populations. Science of the Total Environment. PMID: 11032117.

Stern, A. H., & Smith, A. E. (2003). An assessment of the cord blood:maternal blood methylmercury ratio. Environmental Health Perspectives, 111(12), 1465–1470. https://doi.org/10.1289/ehp.6187

Koenigsmark, F., et al. (2021). Efficacy of hair total mercury as a biomarker in ASGM communities. IJERPH, 18(24), 13350. https://doi.org/10.3390/ijerph182413350

Suárez-Criado, L., et al. (2023). Mercury speciation in human hair from artisanal gold mining regions in Colombia. Environmental Research, 231, 115970. https://doi.org/10.1016/j.envres.2023.115970

Rubin, D. B. (1976). Inference and missing data. Biometrika, 63(3), 581–592. https://doi.org/10.1093/biomet/63.3.581

Che, Z., et al. (2018). Recurrent neural networks for multivariate time series with missing values. Scientific Reports, 8, 6085. https://doi.org/10.1038/s41598-018-24271-9

Agniel, D., Kohane, I. S., & Weber, G. M. (2018). Biases in electronic health record data due to processes within the healthcare system. BMJ, 361, k1479. https://doi.org/10.1136/bmj.k1479

Lundberg, S. M., et al. (2020). From local explanations to global understanding with explainable AI for trees. Nature Machine Intelligence, 2, 56–67. https://doi.org/10.1038/s42256-019-0138-9

Aas, K., Jullum, M., & Løland, A. (2021). Explaining individual predictions when features are dependent. Artificial Intelligence, 298, 103502. https://doi.org/10.1016/j.artint.2021.103502

Bergsma, W. (2013). A bias-correction for Cramér's V and Tschuprow's T. Journal of the Korean Statistical Society, 42(3), 323–328. https://doi.org/10.1016/j.jkss.2012.10.002

Gower, J. C. (1971). A general coefficient of similarity and some of its properties. Biometrics, 27(4), 857–871. https://doi.org/10.2307/2528823

Campello, R. J., Moulavi, D., & Sander, J. (2013). Density-based clustering based on hierarchical density estimates (HDBSCAN). PAKDD, 160–172. https://doi.org/10.1007/978-3-642-37456-2_14

Liu, F. T., Ting, K. M., & Zhou, Z. H. (2008). Isolation Forest. IEEE ICDM, 413–422. https://doi.org/10.1109/ICDM.2008.17

