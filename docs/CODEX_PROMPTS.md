# Prompts de ejecución — copiar a Codex por tarea

Usar el prompt inicial y después el correspondiente a cada tarea. No enviar todos los prompts a agentes simultáneamente antes de cerrar T01. Adjuntar el paquete maestro al repositorio de trabajo. No se requiere acceso a datos reales.

## Prompt inicial (T00 y T01)
> Lee AGENTS.md, TASKS.md y los ocho archivos de los bloques 1–3. Inspecciona el repositorio real y compara HEAD con 56408ec57c98006cfc37df4e3fa3d5ce10867927. Ejecuta T00 sin modificar backend: versiones, manifiesto, carga real, pytest baseline, cohorte keyed en directorio limpio y verificación de hashes. Ejecuta T01 verificando capture_schema.json contra config/schema.json, feature_config.json y consumidores reales. Formaliza interfaces compartidas y reporta discrepancias, campos ambiguos, dependencias y evidencias. No inventes categorías ni conversiones, no cambies hashes ni reentrenes. Si G0 falla, documenta y conserva captura independiente. No hagas push ni despliegue público. Entrega informe y diff; no comiences T02 hasta que el contrato común quede revisado.

## Agente A — T02 y T03
> Implementa storage.py y capture.py conforme DATA_CONTRACT, UI_SPEC y TASKS. Usa UUID, transacciones, FK, snapshots inmutables, control optimista, estados faltantes, PII separada y JSON estricto. Representa los 82 campos originales y operativos aplicables sin duplicar widgets. No modifiques app/app.py; expón interfaces acordadas en T01. Prueba rollback, recuperación, edición, conflictos y aislamiento por caso. Ejecuta C/D/U pertinentes. Entrega diff y evidencia; no persistir audio ni datos reales.

## Agente B — T04 y T05
> Implementa el extractor local spaCy basado en reglas según NLP_SPEC y allowlist de 34 campos. Evidencia y offsets Unicode, negación, incertidumbre, sujeto, temporalidad, contradicción y revisión explícita; sin mutaciones directas. Ejecuta N01–N17. Implementa Vosk local como T05 si las dependencias son compatibles, usando límites y formatos especificados; transcripción editable y fallback manual/texto. No agregues ocupación ni nuevos campos sin aprobación, no uses APIs externas, no edites app/app.py. Reporta WER en fixture real si disponible, no inventes métricas.

## Agente C — T07
> Implementa territorial.py conforme TERRITORIAL_SPEC y contratos de T01/T02: agregación por comunidad con identidad estable, coordenadas ficticias etiquetadas, DBSCAN Haversine, aislados y faltantes visibles, OR-Tools con capacidad y matriz explícita, verificador independiente y demanda no asignada. No uses geocodificación remota ni afirmes rutas viales. Estima solo insumos demostrativos con coeficientes explícitos. Ejecuta pruebas territoriales T01–T06 de TEST_PLAN. No edites app/app.py. Entrega diff y resultados.

## Integrador — T06
> Integra módulos aprobados en app/app.py sin eliminar las tres pestañas existentes ni cambiar backend congelado. Crea adaptador de inferencia por lista positiva y exportador; conserva snapshot prelab, contexto derive y separación lab. Reutiliza funciones reales y muestra aviso experimental. Maneja fallo de artefactos sin st.stop global de captura. Integra propuestas NLP con revisión y estado aislado por caso. Prueba paridad real, M1 invariante ante PII/lab, M3B elegibilidad, unidades y regresión de UI. No inventes salidas si falla el modelo.

## Integrador — T08
> Prepara instalación offline conforme DEPLOYMENT. Resuelve dependencias adicionales bajo restricciones del manifiesto en entorno aislado, pip check, lock y wheelhouse de plataforma destino. Integra P1 verificados; configura localhost y telemetría deshabilitada. Implementa setup/start con preflight y mensajes de error claros. No sobrescribas data/ ni DB existentes. No descargues recursos durante operación. Verifica exclusiones Git y recuperación SQLite. No abras túneles ni publiques.

## QA — T09
> Ejecuta TEST_PLAN y RELEASE_CHECKLIST sobre la versión integrada, conserva XML y acta por prueba, compara baseline, valida invariantes y fixtures. Ejecuta M01–M04 solo si tienes acceso real al equipo y red; si no, marca NOT_RUN e indica pasos manuales. No ocultes fallos/skips. Entrega clasificación de release, limitaciones y comandos de arranque/rollback; ningún despliegue externo ni push sin aprobación. No certifiques uso clínico.
