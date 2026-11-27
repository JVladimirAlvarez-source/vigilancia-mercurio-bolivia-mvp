# DEPLOYMENT — Instalación y operación offline reproducible
Versión 0.1.0 | Plan candidato, no despliegue realizado | Base contrato v2, commit 56408ec57c98006cfc37df4e3fa3d5ce10867927.

## 1. Topología y límites
Computadora local de demostración, Python 3.12, Streamlit en 127.0.0.1, navegador en el mismo equipo, SQLite en data/local/vigilancia.db; spaCy blank('es'), Vosk español local, ML congelado, Plotly sin tiles externos, DBSCAN/OR-Tools. Instalación inicial puede requerir Internet; ejecución y reinstalación desde paquete preparado no deben requerirlo. No es PWA ni Android autónomo. Sin nube, túneles, red pública, push, sincronización ni datos reales. Repositorio auditado público; mantener todos los datos locales fuera de Git. Para otra plataforma construir paquete propio: wheels dependen de SO, arquitectura y Python.

## 2. Inventario y preflight (T00)
Desde raíz, comprobar commit y cambios existentes sin descartar trabajo:
```bash
git rev-parse HEAD
git status --short
python --version
```
Usar Python 3.12 (Windows: py -3.12; Linux: python3.12). Crear .venv y activar (Windows PowerShell `.venv\Scripts\Activate.ps1`; Linux `source .venv/bin/activate`). Si políticas PowerShell bloquean activación, usar directamente `.venv\Scripts\python.exe` sin cambiar políticas. Confirmar intérprete y disco, memoria y micrófono en equipo destino. No imponer hardware mínimo sin mediciones. Verificar que existen config/, src/, models/manifest.json, transformers.joblib y todos los artefactos descritos en manifiesto; reports/ congelados. No cargar joblib de origen no confiable: hashes aseguran coherencia, no autenticidad.

Versiones registradas del manifiesto auditado: numpy 2.3.5, pandas 2.2.3, scipy 1.17.0, scikit-learn 1.9.1, lightgbm 4.7.0, shap 0.54.1, hdbscan 0.8.44, joblib 1.6.0. No asumir disponibilidad de distribuciones ni compatibilidad con spaCy/Vosk/OR-Tools; verificar en equipo destino. Si una versión no está disponible, conservar entorno funcional previo o informar bloqueo; no cambiar manifiesto para ocultarlo. No ejecutar pip upgrade indiscriminado.

## 3. Preparación conectada
1. Instalar requirements-dev.txt en entorno aislado o reutilizar entorno baseline comprobado. Comparar versiones instaladas contra manifest; ejecutar pip check. Para un entorno nuevo, generar constraints del manifiesto antes de resolver:
```bash
python -c "import json,pathlib; p=pathlib.Path('data/local_assets'); p.mkdir(parents=True,exist_ok=True); v=json.loads(pathlib.Path('models/manifest.json').read_text())['versions']; (p/'backend-constraints.txt').write_text(''.join(f'{k}=={x}\n' for k,x in v.items()),encoding='utf-8')"
python -m pip install -r requirements-dev.txt -c data/local_assets/backend-constraints.txt
python -m pip check
python -c "from src.inference import load_artifacts; load_artifacts('models'); print('Backend cargado')"
```
2. Ejecutar baseline pytest. Crear requirements-offline.txt nuevo para dependencias adicionales (spaCy, Vosk, OR-Tools) con versiones seleccionadas tras resolver y verificar. No fijar versiones inventadas. Instalar con constraints y repetir carga y regresión. Si un extra P1 no resuelve, mantenerlo opcional; no bloquear P0. SQLite proviene de stdlib. spaCy blank('es') no requiere descargar modelo lingüístico.
3. Descargar modelo español Vosk de fuente oficial confiable durante preparación, por ejemplo vosk-model-small-es-0.42 si disponible y compatible. Extraer en data/local_assets/vosk-es/; registrar origen, versión, licencia, SHA-256 del archivo y manifiesto de archivos extraídos. No descargar en arranque. Probar audio WAV PCM mono 16 bit 16 kHz. Modelo ausente => voz no disponible y texto/manual activos.
4. Preparar cohorte solo si se necesita demo. Los CSV versionados de mercurio_mvp_v4/ no equivalen a la cohorte keyed. En copia limpia de trabajo y antes de crear registros locales, ejecutar:
```bash
python mercurio_mvp_v4/generate_synthetic_bolivia.py --keyed --out data
```
Nunca ejecutar sobre directorio con datos existentes sin revisar; si data/ contiene assets o DB, generar en staging separado y copiar exclusivamente los seis archivos auditados tras verificar sus hashes, sin sobreescribir información de usuario. Comparar SHA-256 de cada archivo contra manifest data_sha256. Ejecutar audit del backend solo con directorio explícito y reports-dir temporal, nunca sobrescribir reportes congelados. Si difieren, no modificar hashes ni anexar row_id por posición. Modo manual funciona sin cohorte; documentar bloqueo de demo poblacional.

## 4. Empaquetado por plataforma (T08)
Tras resolver entorno limpio y pruebas, producir lock de versiones realmente instaladas y wheelhouse en data/local_assets/ (no versionar). En el mismo SO/arquitectura/Python de destino:
```bash
python -m pip freeze > data/local_assets/requirements-lock.txt
python -m pip download --only-binary=:all: -r data/local_assets/requirements-lock.txt -d data/local_assets/wheelhouse
```
Si freeze contiene rutas locales/editables, sustituirlas por distribuciones reproducibles verificadas antes de descargar. Si falta wheel, construirla en entorno conectado compatible y verificar, o declarar bloqueo. No asumir que pip download completa instalación. Probar en una segunda venv vacía sin Internet:
```bash
python -m pip install --no-index --find-links data/local_assets/wheelhouse -r data/local_assets/requirements-lock.txt
python -m pip check
```
Incluir copia confiable del código con documentos, artefactos congelados y reportes, wheelhouse y lock, modelo Vosk y licencia si distribución permitida, fixture territorial ficticio y opcional cohorte keyed verificada. Excluir .git, .venv, DB/WAL/SHM, audio, transcripciones, backups, secretos y QA con datos. Generar inventario relativo con SHA-256, tamaño, versión, plataforma, commit y fuente; verificar al extraer. No sustituir models/manifest.json. Transferencia local controlada, no publicación. Python y dependencias del sistema (runtime nativo si requerido) deben estar instalados o incluidos por mecanismo autorizado; wheelhouse no instala Python.

## 5. Configuración y arranque
Proponer .streamlit/config.toml fuera de directorios congelados:
```toml
[server]
address = "127.0.0.1"
port = 8501
headless = true
enableXsrfProtection = true

[browser]
gatherUsageStats = false
```
No desactivar controles de seguridad para resolver errores. Ejecutar desde raíz:
```bash
python -m streamlit run app/app.py --server.address 127.0.0.1 --server.port 8501
```
Abrir http://127.0.0.1:8501 en navegador local. Si puerto ocupado, seleccionar otro puerto local explícito, no matar procesos ajenos. Si backend falla, la nueva app debe mostrar bloqueo de inferencia sin impedir captura. La app actual auditada todavía puede detenerse globalmente: la corrección corresponde al integrador, no se afirma resuelta. No utilizar localhost como prueba de ausencia de Internet.

Scripts nuevos propuestos: scripts/setup_offline.py (preflight, verificación inventario, instalación explícita sin red desde wheels; no descarga implícita ni sobrescritura), scripts/start_offline.py (resolver raíz, verificar dependencias esenciales, iniciar subprocess con sys.executable y loopback; sin shell, sin privilegios elevados; indicar fallos). No implementar ni prometer estos scripts en este documento. Opcionales si comandos manuales reproducibles cubren demo.

## 6. Datos persistentes y recuperación
SQLite local con foreign_keys por conexión, transacciones, timeout, control optimista de versiones. Restringir permisos mediante ACL del sistema, no considerar esto cifrado. No almacenar en carpeta sincronizada automáticamente. Para copia consistente usar sqlite3.Connection.backup() con destino fechado en data/local/backups/, o detener toda escritura y usar procedimiento verificado; no copiar solo archivo .db mientras WAL activo. Verificar backup con PRAGMA integrity_check y foreign_key_check, y recuentos/versiones de casos ficticios. Restaurar con aplicación detenida a ruta de staging, verificar y conservar original; reemplazar solo tras aprobación local. No eliminar registros para resolver errores. No versionar backups ni exportaciones. Si falla disco, conservar edición temporal y reportar no guardado; no afirmar recuperación no probada.

## 7. Diagnóstico y contingencias
| Síntoma | Acción |
|---|---|
| SHA-256 distinto | comparar checkout y manifiesto, recuperar copia confiable, bloquear inferencia; no recalcular hashes esperados |
| conflicto de paquetes | volver a entorno baseline, resolver extras aislados; registrar P1 ausente o P0 bloqueado |
| cohorte ausente | captura manual y reportes congelados; no afirmar análisis poblacional de datos inexistentes |
| Vosk/micrófono ausente | texto/manual, indicar RF06 incompleto |
| OR-Tools ausente o sin solución | mantener DBSCAN/demanda, reportar estado; no inventar ruta |
| SQLite bloqueado | timeout y aviso, reintento explícito sin duplicar versión |
| error de integridad DB | detener escrituras, preservar original, restaurar backup verificado |
| puerto ocupado | cambiar puerto loopback, no abrir a 0.0.0.0 |
| falla instalación offline | documentar wheel/runtime faltante, preparar de nuevo conectado, no afirmar paquete reproducible |

## 8. Aceptación y demostración
Ejecutar G0–G5 y M01–M04 de TEST_PLAN. Desde proceso nuevo con red física desconectada: iniciar, ingresar caso ficticio, NLP con negación y confirmación, guardar/reiniciar/recuperar, inferencia real y aviso experimental, laboratorio si procede, territorio con aislados, rutas si solver disponible, exportación segura. Probar voz real si disponible. Mostrar claramente funciones no completadas. Inspeccionar conexiones externas y recursos del navegador. Guardar evidencia local: fecha, plataforma, commit, inventario, versiones, hash manifiesto, resultados pytest, tiempos, prueba de restauración y estado de cada RF. Ningún resultado sintético acredita diagnóstico, prevalencia o ruta vial. No afirmar notificación institucional enviada.

## 9. Entrega y reversión
Entregar paquete local verificable, instrucciones, lock y manifiesto de distribución independiente, acta de QA, lista de limitaciones y estado P0/P1. Conservar baseline y rama de cambios; rollback de código mediante checkout/copia aprobada, nunca git reset --hard ni borrado de datos. Si cambia esquema DB, respaldar y documentar migración y compatibilidad antes de actualizar. No publicar ni hacer push sin autorización. Despliegue privado remoto requeriría decisión separada y no satisface operación autónoma offline; uso real requiere seguridad, gobernanza y validación clínica adicionales.
