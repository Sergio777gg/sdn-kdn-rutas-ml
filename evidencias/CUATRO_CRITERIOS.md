# Comparación de los cuatro criterios

Validación del 9 de noviembre de 2026 en el backend habitual, puerto 8002. Los resultados adjuntos son evidencia histórica; el panel consulta datos recientes al comparar.

- 39 pruebas Python aprobadas y 3 pruebas de la lógica del mapa.
- ESLint y compilación Vite aprobados. La revisión visual automática no estuvo disponible por un fallo del navegador de automatización.
- Los tres cálculos convencionales coinciden con los endpoints anteriores en sus trayectos y costos de selección.
- Las cuatro rutas se evaluaron con una única ventana validada y la misma fórmula QoS. Se conservan los campos anteriores para la tarjeta individual ML.
- No se modificaron controladores, recolectores, datasets ni modelos. Solo se reiniciaron los servicios de interfaz para cargar el cambio.

## Resultados reales S5 → S2

### NSFNET

Sesión: `vivo_nsfnet_20261109T215744Z_c6b9d843`. Observación UTC: `2026-11-09T22:32:08.004947+00:00`.

| Criterio | Trayecto | Saltos | QoS común | Delay previsto ms | Capacidad mínima nominal Mbps |
|---|---|---:|---:|---:|---:|
| Menor nÃºmero de saltos | s5 → s4 → s1 → s2 | 3 | 0.653527 | 76.0751 | 1.5 |
| Menor retardo configurado | s5 → s6 → s3 → s2 | 3 | 0.22262 | 17.7056 | 6.0 |
| Inversa de capacidad nominal | s5 → s6 → s3 → s2 | 3 | 0.22262 | 17.7056 | 6.0 |
| Inteligente ML | s5 → s6 → s3 → s2 | 3 | 0.22262 | 17.7056 | 6.0 |

Menor costo QoS previsto: Menor retardo configurado, Inversa de capacidad nominal, Inteligente ML. Hay empate bajo esta fÃ³rmula. Revisa los otros indicadores: no implica ventaja en todas las mÃ©tricas ni una mejora medida.

### GEANT2

Sesión: `vivo_geant2_20261109T215703Z_29c35a3b`. Observación UTC: `2026-11-09T22:32:15.025844+00:00`.

| Criterio | Trayecto | Saltos | QoS común | Delay previsto ms | Capacidad mínima nominal Mbps |
|---|---|---:|---:|---:|---:|
| Menor nÃºmero de saltos | s5 → s3 → s1 → s2 | 3 | 0.563552 | 73.1696 | 3.0 |
| Menor retardo configurado | s5 → s3 → s4 → s2 | 3 | 0.380862 | 27.4958 | 1.5 |
| Inversa de capacidad nominal | s5 → s3 → s1 → s2 | 3 | 0.563552 | 73.1696 | 3.0 |
| Inteligente ML | s5 → s3 → s4 → s2 | 3 | 0.380862 | 27.4958 | 1.5 |

Menor costo QoS previsto: Menor retardo configurado, Inteligente ML. Hay empate bajo esta fÃ³rmula. Revisa los otros indicadores: no implica ventaja en todas las mÃ©tricas ni una mejora medida.

## Respaldo y reversión

Los cuatro fuentes anteriores se conservan con rutas relativas en `/home/vboxuser/proyecto_nsfnet/backups/comparacion_cuatro_criterios_20261109_222341`. El manifiesto original y el final registran SHA-256.
Para revertir, restaurar esos cuatro archivos desde el respaldo, compilar con `bash scripts/compilar_interfaz.sh` y reiniciar únicamente la interfaz mediante el procedimiento autorizado. Los archivos nuevos pueden conservarse sin uso. No se requiere tocar RYU ni Mininet.
