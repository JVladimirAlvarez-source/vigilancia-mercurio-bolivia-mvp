# Plan de ejecución Codex — seis horas

## Preparación
Extraer paquete en una copia de trabajo del repo, revisando colisiones antes de copiar. No contiene reemplazos de src/config/models. Verificar rama, HEAD, estado limpio o cambios del usuario; no descartarlos. Crear rama de trabajo autorizada; si no hay permiso Git, operar en copia local. Leer AGENTS y TASKS. Ejecutar T00 según DEPLOYMENT y TEST_PLAN; guardar baseline por separado de pruebas finales. Comparar HEAD con commit auditado y reportar cambios relevantes. Si los hashes no coinciden, detener inferencia, no regenerar manifiesto; se permite continuar captura independiente con limitación explícita. G0 fallido impide release P0 aceptado.

## Presupuesto temporal (minutos desde inicio)
| Ventana | Trabajo | Puerta |
|---|---|---|
| 0–30 | T00,T01: preflight y contrato común | G0/G1 o bloqueos explícitos |
| 30–105 | A: T02,T03; B: T04 en paralelo si disponible | persistencia y contrato |
| 105–165 | NLP integrado, revisión y fixtures | G2 |
| 165–195 | T05 voz, si compatible | G4 parcial |
| 195–240 | T07 territorio/rutas; si hay agente C empezar tras T02 | G4 |
| 240–270 | T06 y unión de módulos con interfaz única | G3 |
| 270–340 | T08,T09: regresión, bundle y pruebas físicas | G5 |
| 340–360 | Reserva y demo | acta de release |

Los tiempos son presupuestos, no promesas. T06 puede empezar antes para proteger P0. Si no hay agentes múltiples, ejecutar P0 antes de P1. Congelar ampliaciones al minuto 270; preservar pruebas y operación offline aunque queden P1 pendientes.

## Paralelización y Git
Integrador mantiene contratos comunes, app/app.py, dependencias, configuración y tests/test_app.py. A posee captura y storage; B NLP y voz; C territorio. No editar archivos compartidos en paralelo; usar ramas/worktrees separados si el entorno lo permite. Todos parten del mismo contrato validado T01. Cada agente entrega diff, pruebas, dependencias solicitadas y bloqueos; integrador revisa y combina cambios autorizados en orden T02,T03,T04,T06,T05,T07,T08. No ejecutar merge/push sin autorización; no publicar. Resolver conflictos manualmente, sin sobrescribir trabajo ajeno. Si una interfaz cambia, detener integración y acordar versión compatible.

## Entrega por agente
ID de tarea; commit base; archivos cambiados; interfaces; comandos ejecutados y resultados reales; pruebas PASS/FAIL/SKIP/NOT_RUN; dependencias; limitaciones; próximos pasos. Adjuntar solo evidencia ficticia/desidentificada. El integrador verifica diff y ejecuta pruebas reales del conjunto, no suma resultados de entornos diferentes como si fueran una única corrida.

## Despliegue y demostración
Preparar wheelhouse y recursos locales para SO/arquitectura objetivo conforme DEPLOYMENT. No alojar externamente. Demostrar desde proceso nuevo y red desconectada: ficha manual, NLP, persistencia tras reinicio, M1/SHAP/M3A, laboratorio/M3B, voz y territorio si P1 aprobados, exportación y recuperación. Si Codex no controla el equipo físico, entregar instrucciones M01–M04 y marcar NOT_RUN; no certificar offline. Registrar acta RELEASE_CHECKLIST, rollback y estado completo/parcial/incompleto.
