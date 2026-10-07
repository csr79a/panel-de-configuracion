#!/usr/bin/env bash
# Crea la entrada del menú de aplicaciones para el lanzador.
# Idempotente: se puede ejecutar varias veces; solo reescribe el .desktop.
set -euo pipefail

if [[ $EUID -eq 0 ]]; then
    echo "No ejecutes este script como root; usa tu usuario normal." >&2
    exit 1
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for archivo in "$DIR/lanzador.py" "$DIR/proyectos.json"; do
    if [[ ! -f "$archivo" ]]; then
        echo "ERROR: falta el archivo requerido: $archivo" >&2
        echo "Ejecuta este instalador desde una copia completa del repositorio." >&2
        exit 1
    fi
done

faltan=()
python3 -c 'import PyQt6.QtWidgets' 2>/dev/null || faltan+=("python3-pyqt6")
command -v git >/dev/null 2>&1 || faltan+=("git")
if ((${#faltan[@]})); then
    echo "Faltan paquetes: ${faltan[*]}"
    echo "Instálalos con: sudo apt install ${faltan[*]}"
    exit 1
fi
command -v konsole >/dev/null 2>&1 \
    || echo "AVISO: no está instalado Konsole. Las acciones que necesiten menús/listas o modo terminal requerirán x-terminal-emulator; si tampoco existe, esas acciones no podrán abrirse."

APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS"
cat > "$APPS/panel-de-configuracion.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Panel de Configuración
Comment=Instala y configura aplicaciones y componentes del sistema desde un solo panel
Exec=python3 "$DIR/lanzador.py"
Icon=preferences-system
Terminal=false
Categories=System;Settings;
EOF

command -v update-desktop-database >/dev/null 2>&1 \
    && update-desktop-database "$APPS" || true

echo "Listo: busca «Panel de Configuración» en el menú de aplicaciones."
