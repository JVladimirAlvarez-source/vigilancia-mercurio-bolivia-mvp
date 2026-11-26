# Operación de la interfaz Streamlit

La interfaz usa el backend experimental congelado en `87f02da`. Trabaja desde la raíz del repositorio, con Python 3.12 y una copia de confianza de los artefactos versionados.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python mercurio_mvp_v4/generate_synthetic_bolivia.py --keyed --out data
streamlit run app/app.py
```

Ejecuta el generador en un directorio `data/` vacío al preparar la cohorte por primera vez. El panel comprueba sus huellas contra el manifiesto. Si falta la cohorte, siguen disponibles el ingreso manual y las métricas congeladas. La barra lateral muestra el estado de integridad, la huella del manifiesto, la versión del contrato y métricas de prueba. El cargador prepara el motor una vez por proceso de Streamlit mediante `st.cache_resource`.

## Flujo de trabajo

1. **Triaje prelaboratorio.** Elige una ficha manual o uno de los cuatro casos sintéticos de prueba. Los campos precargados se pueden editar. `Sin dato` conserva el faltante y `No` registra un cero explícito. Indica la compatibilidad clínica únicamente después de evaluarla. Al pulsar **Evaluar ficha**, la aplicación muestra el estado normativo, los datos pendientes, las prioridades, la EDI, el triaje experimental, las contribuciones SHAP y la orientación de matriz y fenotipo.
2. **Auditoría preanalítica.** Usa la ficha evaluada en Triaje o selecciona un ID con medición en `test`. La ficha de demostración precarga las mediciones simuladas, con sus casillas de validación inicialmente desmarcadas. Registra sangre en µg/L y distingue orina en µg/g para la regla normativa de orina en µg/g de creatinina para M3B. La fecha de toma y la demora se traducen a fecha de envío. **Evaluar laboratorio** muestra por separado los errores determinísticos, la clasificación y el resultado estadístico. Cuando el modelo puede puntuar un registro válido, la tabla indica las cuatro señales que recibe el bosque.
3. **Vigilancia poblacional.** Consulta disponibilidad de biomarcadores, prioridades registradas, clasificación obtenida al aplicar las reglas a la ficha, perfiles por partición y métricas de los modelos. La tasa de alertas preanalíticas de 19,8 % corresponde al subconjunto elegible de prueba (35/177).

## Salvaguardas y comprobación

Usa fichas sintéticas durante la demostración. El MVP conserva las fichas manuales en el estado de la sesión de Streamlit. Carece de autenticación, persistencia clínica e integración con sistemas de salud. La cohorte no estima prevalencias de Bolivia. Las probabilidades de M1 son estimaciones experimentales y la alerta de M3B requiere revisión técnica. La confirmación normativa depende de la evaluación profesional y de ambos dosajes validados.

```bash
pytest -v
```

Las pruebas de interfaz usan el motor congelado y verifican los estados Sospechoso, Probable y Confirmado, el manejo de unidades, la ausencia de puntuación sin laboratorio y el caso sintético con discordancia. También comprueban que un artefacto alterado en una copia temporal sea rechazado.

[Contrato del backend](../src/README.md) · [Arquitectura](../docs/ARCHITECTURE.md)
