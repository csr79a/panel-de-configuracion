# Panel de Configuración

Panel gráfico que reúne scripts de configuración del sistema en una sola ventana. Cada botón descarga o actualiza el proyecto desde GitHub y ejecuta su script.

- Ventana hecha con **PyQt6**, con los colores de tu tema de Plasma (claro u oscuro).
- El progreso, las preguntas, los avisos y la contraseña de `sudo` aparecen en la misma ventana.
- No se fuerza `TERM=dumb` en los scripts: ven un terminal interactivo normal.
- Los cuadros `whiptail` de tipo sí/no y aviso se convierten en preguntas de texto; los scripts con menús o listas se abren en **Konsole**.
- El lanzador se inicia como **usuario normal** y no necesita `sudo` por sí mismo.

## Requisitos

- Debian Testing (o derivado basado en APT).
- Los paquetes `python3-pyqt6` y `git`, ambos en los repositorios oficiales.
- `sudo` configurado para tu usuario.
- `konsole` (KDE Plasma): opcional. Solo hace falta si algún script usa menús o listas.

## Uso rápido

sudo apt install python3-pyqt6 git
git clone https://github.com/csr79a/panel-de-configuracion.git ~/panel-de-configuracion
cd ~/panel-de-configuracion
bash instalar-lanzador.sh

Después busca **Panel de Configuración** en el menú de aplicaciones. También puedes abrirlo directamente:

python3 ~/panel-de-configuracion/lanzador.py

## Proyectos incluidos

| Sección | Acción |
| --- | --- |
| Sistema | Sincronizar repositorios APT |
| Sistema | Instalar fuentes de Windows |
| Gaming | Instalar gaming |
| Gaming | Limpiar gaming |
| Rendimiento | Instalar sched-ext |
| Rendimiento | Instalar gestor de sched-ext (GUI) |
| Rendimiento | Desinstalar sched-ext |
| Gráficos NVIDIA | Instalar driver NVIDIA |
| Hardware ASUS | Instalar asusctl / ROG Control |
| Hardware ASUS | Desinstalar asusctl / ROG Control |
| Terminal | Configurar terminal con Starship |

## Contenido de este repo

- lanzador.py — la ventana y la lógica de ejecución.
- proyectos.json — la lista de proyectos, repos y scripts.
- instalar-lanzador.sh — crea la entrada en el menú de aplicaciones.
- scripts/ — scripts propios (por ejemplo, el de fuentes de Windows).
- MANUAL.md — funcionamiento detallado.

## Seguridad

Cada clic ejecuta lo que haya en la rama por defecto del repo correspondiente. Los scripts pueden usar sudo y modificar el sistema según su función. Conviene proteger la cuenta de GitHub con verificación en dos pasos y revisar los cambios de los repos que vayas a ejecutar.
