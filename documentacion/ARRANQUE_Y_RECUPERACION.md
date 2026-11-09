# Arranque y recuperación de las tres VMs

## 1. Consultar antes de iniciar

En cada VM: `hostname -I` e `ip -br a`. Direcciones verificadas el 9 de noviembre de 2026: RYU `.108`, Mininet `.103`, interfaz `.120`, en la red `192.168.56.0/24`. Si cambian, revisar la configuración específica del servicio; no reemplazar direcciones históricas masivamente.

En RYU:

```bash
ss -lntp | grep -E ':(16653|16654|18080|18081|8010)\b'
```

En Mininet:

```bash
sudo ovs-vsctl list-br
ss -lnt | grep -E ':(8768|8769)\b'
```

En interfaz:

```bash
ss -lntp | grep -E ':(8002|8003|5181|5182)\b'
python3 -c "import urllib.request; print(urllib.request.urlopen('http://192.168.56.108:8010/health', timeout=5).read().decode())"
python3 -c "import urllib.request; print(urllib.request.urlopen('http://192.168.56.103:8769/snapshot', timeout=5).status)"
python3 -c "import urllib.request; print(urllib.request.urlopen('http://192.168.56.103:8768/snapshot', timeout=5).status)"
```

Si ya están activos, continuar con ellos. No iniciar duplicados ni liberar puertos matando procesos.

## 2. Iniciar RYU después de apagar las VMs

Solo si los puertos correspondientes están libres, en terminales separadas:

```bash
ryu-manager --ofp-tcp-listen-port 16653 --wsapi-host 0.0.0.0 --wsapi-port 18080 ryu.app.ofctl_rest
```

```bash
ryu-manager --ofp-tcp-listen-port 16654 --wsapi-host 0.0.0.0 --wsapi-port 18081 ryu.app.ofctl_rest
```

Para ML se usa el servidor original que ya está en RYU, con su entorno y modelo existentes. No hace falta clonar GitHub:

```bash
cd ~/proyecto_nsfnet
./entorno_ml/bin/python -u inferencia_comun_v1_hCmIwX/servidor.py \
  resultados_comun_20261107T205101/modelo_20261107T205202Z_n4vncu_0/modelo_comun.pkl
```

El modelo debe conservar `evaluacion_test.json` en su carpeta actual. El servidor verifica la coincidencia de su dataset con el paquete del modelo. No mover, regenerar ni reentrenar esos artefactos.

## 3. Iniciar Mininet después del apagado

Los archivos están instalados en `~/proyecto_nsfnet/laboratorio/mininet/` de la VM Mininet. **No hace falta clonar el repositorio.** Una vez que RYU y el modelo responden, ejecutar un único comando:

```bash
sudo python3 ~/proyecto_nsfnet/laboratorio/mininet/iniciar_redes.py --recuperar-huerfanos
```

El comando inicia primero GEANT2 y después NSFNET, espera una ventana completa con las 60 entradas de todos los enlaces y deja los recolectores funcionando en segundo plano. Al terminar imprime `Ambas redes listas`. Se puede cerrar esa terminal. La carga y el forwarding convencionales son los mismos del experimento; no aplica las decisiones ML al tráfico.

Si una red ya tiene observador y mediciones recientes, la verifica y la conserva. Se probó repetir la orden: mantuvo los mismos procesos y no duplicó redes.

Después de apagar una VM, OVS puede conservar los bridges aunque sus interfaces `*-eth*` hayan desaparecido. RYU puede mostrar 24 y 14 switches que solo tienen el puerto local. Eso no demuestra que las redes y sus recolectores estén activos.

La opción `--recuperar-huerfanos` autoriza, en esta ejecución, retirar exclusivamente esos restos tras comprobar DPID, controlador, nombres de puertos, ausencia de interfaces Linux y ausencia de procesos propietarios. Se guarda un respaldo completo de OVS antes de retirar nada. Una identidad o estado dudoso cancela la operación; no se ejecuta `mn -c`, no se reinicia RYU ni se detiene un recolector existente. Sin esa opción, el comando se limita a conservar los restos y explicar la situación.

Los respaldos quedan bajo `~/proyecto_nsfnet/backups/recuperacion_ovs_<fecha>/`. Los logs del arranque se guardan bajo `laboratorio/mininet/arranques/<fecha>/` y las ventanas nuevas bajo `laboratorio/mininet/sesiones/`. No se reutilizan PID históricos ni se sobrescriben las sesiones anteriores.

**Validación real:** se recuperaron los 24 bridges GEANT2 y los 14 NSFNET que quedaron después del apagado, se iniciaron los dos recolectores, se verificaron entradas recientes y se calcularon ambas alternativas de ruta con el modelo original. La evidencia está en `evidencias/RECUPERACION_TRAS_APAGADO.md`.

## 4. Iniciar la interfaz

Se reutilizan `.venv` y `frontend/app/node_modules`. En el proyecto de interfaz:

```bash
cd ~/proyecto_nsfnet
bash scripts/compilar_interfaz.sh
```

En terminales separadas, cuando los puertos habituales estén libres:

```bash
bash scripts/iniciar_backend.sh
```

```bash
bash scripts/iniciar_frontend.sh
```

Abrir `http://127.0.0.1:5181/sdn-selector.html` **en la VM de interfaz**. Elegir NSFNET o GEANT2; no configurar manualmente el puerto del observador. Los scripts se niegan a ocupar puertos ya utilizados a través de Uvicorn/Vite; no detienen procesos para liberarlos.

Para una validación paralela, usar `SDN_API_PORT=8003`, compilar con `VITE_SDN_SELECTOR_API_URL=http://127.0.0.1:8003 SDN_DIST_DIR=dist-rutas-ml-validacion`, e iniciar frontend con `SDN_FRONTEND_PORT=5182 SDN_DIST_DIR=dist-rutas-ml-validacion`. Esa variante está disponible en esta entrega; no iniciar otra si esos puertos ya están ocupados.

## 5. Detener, recuperar y revertir

- **Consultar:** los comandos de la sección 1 no cambian la red.
- **Iniciar:** secciones 2–4 solo cuando no existen los servicios y redes correspondientes.
- **Detener:** Ctrl+C en la terminal propietaria de un servicio de interfaz. Para detener una red Mininet se requiere autorización: Ctrl+C en su worker cierra sus hosts, interfaces y sondas. No reutilizar PID del informe; consultar el estado y el proceso actual.
- **Recuperar:** si un puerto está ocupado o quedan bridges, inspeccionar identidad y estado. No borrar ni detener automáticamente nada. Resolver con el operador antes de repetir el arranque.
- **Revertir código:** seguir `RESPALDO_Y_ROLLBACK.md`. No restaurar modelos, datasets ni carpetas de telemetría para revertir esta ampliación.

Los logs nuevos se separan de los históricos. Los instaladores y launchers antiguos con PID fijos no deben reutilizarse como guía del próximo arranque.
