# Comparación SDN/KDN

## Cuatro criterios en la comparación

La comparación conjunta calcula una ruta óptima para cada criterio del selector: saltos, retardo configurado, inversa de capacidad nominal y QoS direccional ML. Las tres primeras reutilizan Dijkstra y sus pesos existentes. Todas se evalúan sobre el mismo snapshot; se realiza una única obtención validada de predicciones para evaluar los cuatro caminos bajo el mismo QoS.

`alternativas` contiene los cuatro resultados, su estado, costo de selección con sus unidades, métricas comunes, coincidencias, diferencias frente a la referencia por capacidad, ventajas y desventajas. `mejores_por_metrica` identifica mejores valores y empates con tolerancia numérica. Los campos `convencional` e `inteligente` se conservan para compatibilidad con la tarjeta individual y los clientes existentes.

Los costos de selección de saltos, ms configurados, Σ 1/Mbps y QoS tienen distintas escalas y se etiquetan por columna. Las comparaciones numéricas entre caminos usan métricas comunes. La capacidad mínima se favorece al aumentar; los costos, saltos y retardos/pérdidas se favorecen al disminuir. Las ventajas y desventajas textuales son relativas a la ruta por inversa de capacidad. No se deduce un throughput extremo a extremo.

Cuando varias opciones eligen el mismo camino, se conservan sus columnas y se declara la coincidencia. Si falta ML, se muestran las tres alternativas convencionales sin métricas previstas. Si falta retardo configurado, únicamente esa alternativa se declara no disponible; no se omiten enlaces silenciosamente para favorecerla.

## Flujo de datos

Mininet conserva sus redes y recolectores. Los observadores publican topologías, interfaces y ventanas medidas. FastAPI selecciona la fuente permitida y verifica DPID y nombres de puertos contra RYU. El servicio ML existente en RYU recibe las 60 características por enlace y devuelve seis predicciones para la ventana siguiente. FastAPI calcula los dos caminos; React los presenta sobre el mismo mapa existente. El tráfico no pasa por FastAPI.

La cadena lógica es Mininet → observador → FastAPI → inferencia en RYU → FastAPI → React. RYU también suministra identidad y estado OpenFlow. No se modifica el plano de datos al comparar.

## Referencia conservada

`backend/algoritmos/dijkstra.py` y `pesos.py` permanecen intactos. La referencia utiliza el Dijkstra existente con costo por enlace `1 / capacidad_mbps`, sobre enlaces verificados activos de la topología seleccionada. No maximiza necesariamente el cuello de botella. `/api/sdn/rutas` conserva sus criterios y comportamiento.

## Costo ML direccional

Para cada dirección: `d` es delay previsto en ms; `l`, loss previsto como razón [0,1]; `c`, capacidad nominal en Mbps; `t`, throughput RX previsto en Mbps.

```
Q = wd · d/(d+D) + wl · l/(l+L) + wc · C/(C+c) + wt · t/(t+c)
```

Valores iniciales: `wd=0.50`, `wl=0.35`, `wc=0.15`, `wt=0`; `D=50 ms`, `L=0.01`, `C=1 Mbps`. El backend normaliza los pesos para sumar uno. Todos los componentes son adimensionales y están entre cero y uno; sus sumas por camino no tienen unidades físicas. Las escalas son umbrales de diseño explícitos, no parámetros aprendidos ni una optimización validada experimentalmente. `D` da sensibilidad al orden de retardos configurados del laboratorio; `L` hace visible una pérdida del 1%; `C` ofrece una penalización acotada a capacidades bajas. Deben ajustarse a los objetivos del experimento.

Delay y loss reciben mayor prioridad por su impacto en QoS. El término de capacidad evita favorecer exclusivamente caminos de capacidad nominal pequeña. Las tres escalas son configurables mediante `escalas` en la API; los cuatro pesos están disponibles en la interfaz. No hay min-max calculado con test ni reentrenamiento.

El término de RX queda desactivado por defecto. RX bajo puede indicar baja demanda, no mala calidad. Si el usuario activa `load`, `t/(t+c)` se interpreta exclusivamente como un proxy creciente y acotado de tráfico cursado relativo a capacidad nominal. Puede subestimar congestión cuando se pierden paquetes; no estima capacidad libre ni demanda ofrecida. Nunca se utiliza `1/t`. La predicción RX se muestra por enlace incluso con peso cero.

Se construyen ambos arcos `u→v` y `v→u`, usando los nombres reales de los seis targets. El grafo ML es dirigido. Los valores deben ser finitos y no negativos; loss debe permanecer en [0,1], capacidad y escalas deben ser positivas. Los pesos no pueden sumar cero.

## Comparación y temporalidad

`POST /api/sdn/rutas/comparar` recibe origen, destino, `topology_instance_id`, `graph_version`, `selection_revision`, pesos y escalas opcionales. El cliente no suministra el grafo ni URLs arbitrarias.

Se congela un snapshot verificado, se validan todas las entradas de todos los enlaces activos y se exige una única ventana común. Se reutilizan `_entrada`, `_validar_salida` y `_predecir` del módulo existente. Se comprueban topología, sesión, enlace, fechas de medición, método de sondas, las 60 características exactas, capacidad concordante con el perfil, esquema, seis salidas, modelo y frescura. El límite de 120 segundos se confirmó tanto en `servidor.py` como en `/schema`. El servicio ML no transporta instancia ni versión: estas se vinculan al contexto y al hash exacto de las entradas en FastAPI, y se vuelven a verificar contra la red antes de responder.

La caché separa fuente, topología, sesión, instancia, grafo, revisión de selección, modelo y hash de entradas. Una respuesta de caché pasa de nuevo por validación. Una ventana nueva durante el cálculo no invalida la anterior mientras siga reciente y no cambie el grafo. El panel muestra la ventana fijada y retira el resultado ML al caducar. Un cambio de origen, destino, selección, sesión o grafo invalida resultados y consultas pendientes.

Si falta una predicción, falla el servicio o caducan las entradas, se conserva el cálculo convencional y se informa que ML no está disponible. No se completa el grafo con métricas convencionales ni se optimiza silenciosamente un subgrafo con predicciones incompletas. Un cambio de identidad durante la solicitud devuelve 409.

Ambos caminos se evalúan bajo la misma fórmula QoS y las mismas predicciones. El costo de referencia también se calcula para ambos. No se comparan directamente costos de fórmulas diferentes. Si coinciden los caminos, se informa sin forzar una diferencia.

Delay de camino = suma de delays previstos; es una estimación por enlaces. Loss = `1 - producto(1-loss_enlace)`; aproxima pérdidas sucesivas y no acredita independencia ni una medición extremo a extremo. El target de este recolector incluye rechazos locales de envío de sondas. La capacidad mínima es nominal. No se suman throughputs RX ni se informa un throughput extremo a extremo ficticio.

## Selector y límites

Las fuentes se centralizan en `fuentes_sdn.py`, con variables de entorno por topología. `/seleccionar` usa el observador propio y filtra su lista por topología y sesión: el observador 8769 realmente publica ambas redes. `/fuente` se conserva para compatibilidad, pero solo acepta fuentes de la lista del servidor. El controlador publicado debe coincidir con IP, REST y puerto OpenFlow configurados. Auto mantiene la topología actual mientras su sesión sea observable; si deja de estar disponible, prueba NSFNET y después GEANT2. Varias sesiones de una misma topología exigen selección explícita.

La selección sigue siendo global al proceso FastAPI, como en el proyecto original; varios navegadores comparten selección. No hay autenticación multiusuario ni distribución entre varios workers. Un fallo de RYU se muestra como tal: Auto no usa ese fallo para conmutar por sí solo si el observador sigue publicando la sesión.

La recomendación minimiza un costo previsto, no demuestra una mejora en tráfico real. Aplicar forwarding ML, controlar oscilaciones, validar métricas extremo a extremo y evaluar coeficientes con una campaña autorizada son tareas futuras. No se instalaron reglas OpenFlow en estas pruebas.
