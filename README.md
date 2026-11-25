
#  Construcción del Dataset Sintético (`N = 1,500`, `seed = 42`)

Ante la ausencia de microdatos clínicos públicos en Bolivia, los datos (`ficha_mercurio_bolivia_v2.csv`, 87 columnas) se generaron mediante **simulación estocástica causal por variables latentes** para garantizar coherencia biológica y evitar filas aleatorias sin sentido clínico:

* **Flujo Causal:** `Escenario latente (Z)` $\rightarrow$ `Exposición y temporalidad` $\rightarrow$ `Biomarcadores lognormales (B)` $\rightarrow$ `Manifestaciones clínicas (S)` $\rightarrow$ `Perturbaciones y faltantes`.
* **5 Escenarios Epidemiológicos Latentes:** Exposición alimentaria predominante a $\text{MeHg}$ (30 %), exposición ocupacional a $\text{Hg}^0$ (25 %), exposición mixta (20 %), exposición inorgánica a $\text{Hg}^{2+}$ (10 %) y controles de baja exposición (15 %). Incluye transversales de vulnerabilidad (embarazo, lactancia, menores de 18 años).
* **Calibración Empírica:** Concentraciones ícticas calibradas con datos del río Beni (Loayza et al., 2026: *mota* $1{,}9 \pm 1{,}0\ \mu\text{g/g}$), mediana capilar de $4{,}0\ \mu\text{g/g}$ (Benefice et al., 2008), semivida de $\text{MeHg}$ de 50 días y umbrales urinarios HBM-II ($20\ \mu\text{g/g Cr}$) y Guía N.º 537 ($50\ \mu\text{g/g Cr}$).
* **Realismo Clínico y Preanalítico:** Los 30 síntomas oficiales se generan vía modelos logísticos condicionados a la carga tóxica y susceptibilidad individual. Se incorporan datos faltantes (*MAR/MNAR*, ~13 %) y ~8 % de anomalías inyectadas (contaminación externa de cabello, discordancias y errores de escala) exclusivamente sobre registros con laboratorio.
* **Separación Física Anti-Leakage:** El generador exporta matrices separadas (`X_M1`, `X_M3A`, `X_M3B`, `Y`) y aísla las variables latentes en `auditoria_latente_NO_ENTRENAR.csv`.

> **Alcance:** Las proporciones de cohortes, tasas de anomalía y probabilidades sintomáticas específicas son supuestos de simulación del MVP; las métricas de los modelos miden coherencia del simulador, no validez diagnóstica en población real.

---

## 2. Arquitectura del Sistema

| Capa | Algoritmo / Lógica | Entrada | Función |
| :--- | :--- | :--- | :--- |
| **Capa 1 — Motor Normativo** | Reglas Guía N.º 537 + $EDI$ | Ficha pre-lab | Clasificación oficial (*Probable / Confirmado*), alertas materno-infantiles e ingesta diaria estimada. |
| **Capa 2 — Triaje Predictivo** | `LightGBM + SHAP` | `X_M1` (63 cols) | Riesgo pre-laboratorio de $\text{MeHg}$ (cabello $\ge 3$ y $\ge 5\ \mu\text{g/g}$) y $\text{Hg}^0$ (orina $\ge 20$ y $\ge 50\ \mu\text{g/g Cr}$). |
| **Capa 3A — Fenotipado** | `Gower + HDBSCAN` | `X_M3A` (63 cols) | Agrupamiento no supervisado de perfiles clínicos ($\text{Hg}^0$ vs. $\text{MeHg}$ vs. mixto). |
| **Capa 3B — Auditoría** | `Isolation Forest` | `X_M3B` (66 cols) | Alerta de discordancias clínico-toxicológicas, posible contaminación capilar o errores de unidad. |

---

## 3. Estructura y Ejecución

``````text
vigilancia_mercurio_bolivia/
├── app/app.py                          # Interfaz clínica (Streamlit)
├── data/                               # Dataset maestro, matrices X/Y y validación JSON
├── models/                             # Modelos entrenados (.joblib)
└── src/
    ├── generate_synthetic_bolivia.py   # Generador causal v2.0
    ├── features_pipeline.py            # Motor Guía 537 + limpieza
    └── train_models.py                 # Entrenamiento y evaluación

``````

## Ejecución Rápida
```bash
pip install -r requirements.txt
python src/generate_synthetic_bolivia.py --out ./data

```

4. Referencias Científicas y Normativas
Ministerio de Salud y Deportes de Bolivia (2024). Guía Técnica N.º 537: Vigilancia Epidemiológica y Atención Integral de la Intoxicación por Mercurio.

Clarkson, T. W., & Magos, L. (2006). The toxicology of mercury and its chemical compounds. Critical Reviews in Toxicology, 36(8), 609–662. https://doi.org/10.1080/10408440600845619

ATSDR (2024). Toxicological Profile for Mercury. https://www.atsdr.cdc.gov/toxprofiles/tp46.pdf

WHO / UNEP (2008). Guidance for Identifying Populations at Risk from Mercury Exposure. https://www.who.int/publications/m/item/guidance-for-identifying-populations-at-risk-from-mercury-exposure

Loayza, E., et al. (2026). Concentraciones de mercurio en especies ícticas de la cuenca amazónica boliviana (río Beni). Journal of Food Composition and Analysis. https://doi.org/10.1016/j.jfca.2025.108840

Benefice, E., Luna-Monrroy, S., & Lopez-Rodriguez, R. (2008). Fishing activity, health characteristics and mercury exposure of Amerindian women living along the Beni River. IJHEH. https://pubmed.ncbi.nlm.nih.gov/19004394/

Feingold, B. J., et al. (2020). Population-based hair mercury concentrations in Madre de Dios, Peru. Environmental Research, 180, 108720. https://doi.org/10.1016/j.envres.2019.108720

Diringer, S. E., et al. (2015). River transport of mercury from artisanal and small-scale gold mining in Madre de Dios, Peru. Environ. Sci.: Processes Impacts, 17(2), 478–487. https://doi.org/10.1039/C4EM00567H

Sánchez Rodríguez, L. H., et al. (2017). Mercury levels in blood, urine and hair of artisanal gold miners in Colombia. Toxicology and Industrial Health. https://doi.org/10.1177/0748233716659031

Lebel, J., et al. (1998). Neurotoxic effects of low-level methylmercury contamination in the Amazonian Basin. Environmental Research, 79(1), 20–32. https://doi.org/10.1006/enrs.1998.3846

CDC — NHANES. Speciated Blood Mercury & Urinary Mercury Reference Distributions. https://wwwn.cdc.gov/nchs/nhanes/

Koenigsmark, F., et al. (2021). Efficacy of hair total mercury as a biomarker in ASGM communities. IJERPH, 18(24), 13350. https://doi.org/10.3390/ijerph182413350

Suárez-Criado, L., et al. (2023). Mercury speciation in human hair from artisanal gold mining regions in Colombia. Environmental Research, 231, 115970. https://doi.org/10.1016/j.envres.2023.115970

Rubin, D. B. (1976). Inference and missing data. Biometrika, 63(3), 581–592. https://doi.org/10.1093/biomet/63.3.581

Lundberg, S. M., et al. (2020). Explainable AI for trees. Nature Machine Intelligence, 2, 56–67. https://doi.org/10.1038/s42256-019-0138-9

Gower, J. C. (1971). A general coefficient of similarity. Biometrics, 27(4), 857–871. https://doi.org/10.2307/2528823

Campello, R. J., Moulavi, D., & Sander, J. (2013). Density-based clustering (HDBSCAN). PAKDD, 160–172. https://doi.org/10.1007/978-3-642-37456-2_14

Liu, F. T., Ting, K. M., & Zhou, Z. H. (2008). Isolation Forest. IEEE ICDM, 413–422. https://doi.org/10.1109/ICDM.2008.17



