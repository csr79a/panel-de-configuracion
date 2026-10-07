# Manual del Panel de Configuración

## 1. Qué hace y qué no hace

El panel es una ventana que muestra una lista de acciones agrupadas por secciones. Al pulsar **Ejecutar** en una acción:

1. La ventana pasa a la vista de ejecución: un panel de registro, un campo de respuesta y el botón **Cancelar**.
2. Si el proyecto no está descargado, lo clona con `git clone`. Si ya está, ejecuta `git pull --ff-only`.
3. Si la acción lleva `apt_update: true`, ejecuta `sudo apt update`.
4. Ejecuta el script según el `modo` definido en `proyectos.json`.
5. Al terminar muestra el resultado (completado, falló con su código o cancelado).

El panel no modifica los scripts descargados y no ejecuta nada como root por su cuenta. Se niega a arrancar si lo lanzas como root.

## 2. Modos de ejecución

Cada acción puede llevar el campo `modo` en `proyectos.json`:

| Modo | Qué hace |
| --- | --- |
| `auto` (por defecto) | Ejecuta el script dentro de la ventana. Si usa menús, listas, campos de texto o `dialog`, lo abre en Konsole. |
| `integrado` | Siempre dentro de la ventana, aunque el script tenga menús. |
| `gui` | Para scripts que abren su propia aplicación: actualiza el proyecto en la ventana y lanza el script sin terminal. |
| `terminal` | Siempre en Konsole. |

## 3. Cuadros whiptail dentro de la ventana

Mientras un script corre dentro de la ventana, el panel pone por delante en el `PATH` un `whiptail` de texto propio. Convierte:

- `--yesno` en una pregunta `s/n`.
- `--msgbox` en un aviso con «Pulsa Enter para continuar».
- `--infobox` en un mensaje sin pausa.

Los scripts no se modifican: en una terminal normal siguen usando el `whiptail` real.

## 4. Instalación

```bash
sudo apt install python3-pyqt6 git
git clone https://github.com/csr79a/panel-de-configuracion.git ~/panel-de-configuracion
cd ~/panel-de-configuracion
bash instalar-lanzador.sh
