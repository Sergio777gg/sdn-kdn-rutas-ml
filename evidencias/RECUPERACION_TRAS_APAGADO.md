# Recuperación tras apagar las VMs

Validación realizada el 9 de noviembre de 2026. RYU y ML estaban iniciados; Mininet no tenía recolectores ni observadores. OVS conservaba 38 bridges y 154 referencias a interfaces inexistentes. Los dos REST mostraban los switches, pero sus descripciones solo contenían los puertos locales.

## Operación autorizada

Se retiraron únicamente los restos `nc1`–`nc24` y `ns1`–`ns14`, después de verificar ausencia de enlaces Linux y de procesos propietarios, identidad de DPID/controlador y pertenencia de los puertos al perfil. Se crearon respaldos OVS independientes para cada topología. No se ejecutó `mn -c` ni se reiniciaron los controladores o el modelo.

## Resultado

- GEANT2: 24 nodos y 37 enlaces con 60 características recientes por enlace.
- NSFNET: 14 nodos y 21 enlaces con 60 características recientes por enlace.
- El backend verificó interfaces y puertos OpenFlow; las comparaciones reales convencional/ML aprobaron en ambas redes.
- Al repetir el arranque se conservaron los mismos dos procesos recolectores; no se duplicaron redes.
- 30 pruebas automáticas aprobadas. Las nuevas prueban que una interfaz Linux existente, un propietario activo, un DPID/controlador diferente o un puerto desconocido impiden retirar bridges.
- Los SHA-256 de los 44 CSV originales y del modelo coinciden con los anteriores al desarrollo.

Los JSON adjuntos contienen evidencia fechada, no predicciones actuales. Los PID son evidencia puntual y no instrucciones de arranque o detención. Los respaldos completos de OVS permanecen en Mininet y no se publican.
