# Contribuir

Este repositorio reúne la interfaz y la integración de un laboratorio académico con tres VMs. La comparación calcula decisiones; no las aplica al plano de datos.

## Preparar una contribución

1. Crear una rama para el cambio y explicar el problema concreto.
2. Conservar Dijkstra convencional, dataset y modelo entrenado como referencia.
3. Añadir pruebas cuando cambie la lógica de rutas, el contrato de inferencia o la selección de fuentes.
4. Abrir un pull request con descripción del comportamiento final, pruebas y límites conocidos.

## Pruebas aisladas

En un entorno de desarrollo nuevo, separado de las VMs activas:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-ci.txt
python -m pytest tests -q
```

GitHub Actions ejecuta estas pruebas sin contactar Mininet ni RYU. `requirements-ci.txt` define dependencias compatibles para CI; `requirements.txt` conserva el inventario original del entorno del laboratorio.

## Frontend

En la VM se reutiliza el entorno Node y `node_modules` existente. En un clon nuevo, dentro de `frontend/app`, usar `npm ci` para reproducir `package-lock.json`. Compilar la entrada del selector con `npm run build -- --config vite.sdn-selector.config.js`. La guía de arranque explica los directorios de salida usados para conservar las compilaciones anteriores.

La comprobación de los archivos de esta ampliación es:

```bash
cd frontend/app
npx eslint src/sdn-selector-v2/ComparacionRutas.jsx src/sdn-selector-v2/SelectorRoot.jsx src/sdn-selector-v2/PanelSdn.jsx
```

La lógica pura de visibilidad y agrupación de las cuatro rutas se prueba sin instalar dependencias adicionales:

```bash
node --test frontend/app/tests/comparisonGraph.test.mjs
```

Ejecutar esa última orden desde la raíz del repositorio. GitHub Actions la ejecuta además de las pruebas Python. La compilación Vite y la validación con las VMs se registran por separado.

## Cambios en las VMs

Inspeccionar antes de editar, respaldar con fecha y registrar SHA-256. No detener recolectores, reiniciar controladores, limpiar Mininet, generar campañas, modificar modelos/datasets ni instalar forwarding sin autorización explícita del operador. Las pruebas reales son opt-in y están separadas de CI.

No incluir credenciales, modelos, CSV originales, entornos, logs ni respaldos en los commits. Los resultados de `evidencias/` corresponden a una ejecución fechada y no deben usarse como telemetría actual.
