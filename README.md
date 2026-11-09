# SDN/KDN — comparación de rutas NSFNET y GEANT2

[![Validación](https://github.com/Sergio777gg/sdn-kdn-rutas-ml/actions/workflows/validacion.yml/badge.svg)](https://github.com/Sergio777gg/sdn-kdn-rutas-ml/actions/workflows/validacion.yml)

Ampliación del proyecto existente FastAPI/React/RYU/Mininet. Compara Dijkstra con costo inverso de capacidad y Dijkstra dirigido con costos QoS basados en las predicciones del modelo común existente. No reentrena el modelo ni instala forwarding al comparar.

## Estado de esta entrega

- Código activado en `/home/vboxuser/proyecto_nsfnet` de la VM de interfaz, con autorización del usuario.
- Versión de validación: backend `127.0.0.1:8003`; panel `http://127.0.0.1:5182/sdn-selector.html` dentro de esa VM.
- Versión habitual activada: FastAPI `127.0.0.1:8002` y panel `http://127.0.0.1:5181/sdn-selector.html`. Se reiniciaron únicamente FastAPI y Vite; RYU, ML y recolectores conservaron sus procesos originales.
- 30 pruebas automáticas aprobadas, incluidas las originales y las de recuperación OVS; comparación real aprobada para ambas topologías. Evidencias en `evidencias/`.
- Frontend compilado y archivos modificados aprobados por ESLint. Revisión visual e interacción completa pendientes: Computer Use se detuvo al no poder verificar la URL del navegador.
- Repositorio público: [Sergio777gg/sdn-kdn-rutas-ml](https://github.com/Sergio777gg/sdn-kdn-rutas-ml).

## Uso

1. Abrir `http://127.0.0.1:5181/sdn-selector.html` en la VM de interfaz.
2. Pulsar NSFNET o GEANT2. No escribir IP ni puertos del observador.
3. Esperar «Red activa verificada». Revisar telemetría y disponibilidad del modelo por separado.
4. Ir a **Enrutamiento**, elegir origen y destino. Para la tarjeta individual, seleccionar **Ruta inteligente (ML)** en **Criterio de la ruta** y pulsar **Calcular ruta inteligente**. Para evaluar las dos alternativas juntas, pulsar **Comparar rutas**.
5. Revisar trayectos, costos bajo ambas fórmulas, delay previsto, loss compuesto y capacidad mínima nominal. Se indica si los caminos coinciden.
6. Usar las casillas para ocultar o mostrar trazados sin recalcular. Azul continuo = convencional; violeta discontinuo = ML; dorado punteado = tramos compartidos.
7. Abrir las predicciones por enlace de cada ruta. Esas tablas conservan la ventana de la comparación; al seleccionar el enlace, el inspector existente puede mostrar una ventana más nueva.

La comparación no aplica las rutas al tráfico. Si las entradas faltan o caducan, solo se ofrece el cálculo convencional. El panel retira resultados ML a los 120 segundos desde el final de la ventana de entrada. Las predicciones son para la próxima ventana.

## Archivos principales

| Archivo | Responsabilidad |
|---|---|
| `backend/servicios/fuentes_sdn.py` | Fuentes configuradas, filtro de sesión y Auto estable |
| `backend/servicios/comparacion_rutas.py` | Costos direccionales y evaluación común de caminos |
| `backend/api/sdn_comparacion.py` | Snapshot fijado, inferencia validada y endpoint de comparación |
| `backend/api/sdn_selector_v2.py` | Integración de fuentes y router nuevo |
| `frontend/app/src/sdn-selector-v2/ComparacionRutas.jsx` | Formulario, tarjetas, tabla y predicciones fijadas |
| `SelectorRoot.jsx`, `PanelSdn.jsx` en la misma carpeta | Selector automático, invalidación y trazados sobre el mapa existente |
| `tests/test_comparacion_rutas.py` | Casos sintéticos de algoritmo, datos inválidos y fuentes |
| `tests/validar_en_vivo.py` | Validación explícita contra las dos redes existentes |

## Arranque, arquitectura y reversión

En Mininet, los archivos ya instalados se inician con un solo comando, sin clonar GitHub:

```bash
sudo python3 ~/proyecto_nsfnet/laboratorio/mininet/iniciar_redes.py --recuperar-huerfanos
```

Consultar [guía de arranque](documentacion/ARRANQUE_Y_RECUPERACION.md), [costo y arquitectura](documentacion/ARQUITECTURA_Y_COSTO.md), [respaldo y reversión](documentacion/RESPALDO_Y_ROLLBACK.md) y [evidencias](evidencias/RESULTADOS.md).

Las dependencias de Python y npm del proyecto se conservan; no se reinstalaron ni actualizaron bibliotecas en las VMs. Para comprobar sobre su entorno existente:

```bash
cd ~/proyecto_nsfnet
.venv/bin/python -m pytest tests -q
SDN_TEST_API=http://127.0.0.1:8003 .venv/bin/python tests/validar_en_vivo.py
```

La segunda orden realiza consultas e inferencias reales y cambia la selección del backend probado. Usar el puerto de validación mientras se revisa el proyecto.

## GitHub

Para colaborar, consultar [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) y el [registro de cambios](CHANGELOG.md). GitHub Actions ejecuta las pruebas Python en un entorno aislado, sin conectarse a las VMs; las pruebas reales y la compilación del frontend verificadas en el laboratorio se documentan en `evidencias/`. La documentación histórica `SDN_VIVO_V1_LEEME.md` describe una integración anterior; las guías enlazadas en este README corresponden a esta versión.

```bash
git clone https://github.com/Sergio777gg/sdn-kdn-rutas-ml.git
cd sdn-kdn-rutas-ml
```

El repositorio preparado excluye contraseñas, llaves, `.env`, modelos, datasets, logs operativos, respaldos y dependencias instaladas. Las evidencias de rutas incluidas son resultados fechados y no una fuente de predicciones actuales. No se añade licencia porque corresponde decidirla al propietario del proyecto.

Los modelos y los CSV originales permanecen en las VMs; no forman parte de este paquete. Los hashes de conservación se incluyen para verificar que no cambiaron. Los scripts bajo `laboratorio/` son copias de recuperación de las fuentes realmente inspeccionadas, con un envoltorio nuevo de arranque explícito. No se ejecutaron sobre las redes activas.

## Límites pendientes

Revisión visual manual pendiente. La activación en los puertos habituales está completada y verificada por HTTP. Se verificó la recuperación de Mininet con restos OVS reales tras el apagado de las VMs, conservando los controladores y sin duplicar recolectores. Multiusuario, autenticación, aplicación de rutas ML y evaluación experimental de mejoras quedan fuera de esta ampliación.
