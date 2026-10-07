#!/usr/bin/env python3
"""Panel de Configuración: ventana que reúne los scripts de
configuración del sistema (PyQt6).

Cada botón clona o actualiza el repo del proyecto y ejecuta su script tal cual,
sin modificarlo. El lanzador corre como usuario normal.

Modos de ejecución (campo "modo" de cada acción en proyectos.json):

  auto        (por defecto) El script se ejecuta DENTRO de esta ventana, en un
              pseudo-terminal: salida con colores, preguntas (read) y contraseña
              de sudo se responden en la propia ventana. Los cuadros whiptail
              --yesno/--msgbox/--infobox se convierten a preguntas de texto con
              un whiptail propio (solo existe mientras corre el script aquí).
              Si el script usa menús, listas, campos de texto o dialog, se abre
              en Konsole.
  integrado   Igual que auto, pero nunca cae a Konsole.
  gui         Para scripts que abren su propia aplicación gráfica: el proyecto se
              actualiza aquí y el script se lanza sin terminal.
  terminal    Siempre en Konsole, como en la versión anterior.
"""
import codecs
import fcntl
import json
import os
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
from pathlib import Path

from PyQt6.QtCore import (QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt,
                          QTimer, pyqtSignal)
from PyQt6.QtGui import (QColor, QFontDatabase, QIcon, QTextCharFormat,
                         QTextCursor)
from PyQt6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect,
                             QGraphicsOpacityEffect, QGridLayout, QHBoxLayout,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QMessageBox, QPlainTextEdit, QPushButton,
                             QScrollArea, QSizePolicy, QStackedWidget,
                             QVBoxLayout, QWidget)

CONFIG = Path(__file__).resolve().parent / "proyectos.json"
LOG_DIR = Path.home() / ".local/share/panel-de-configuracion/logs"
MODOS = ("auto", "integrado", "gui", "terminal")

# Icono del tema, emoji de reserva y color de acento por sección. Si una
# sección no aparece aquí se usa el valor por defecto (icono genérico).
SECCIONES = {
    "Base":            ("preferences-system", "\u2699", "#4f9cf0"),
    "Sistema":         ("preferences-system", "\u2699", "#4f9cf0"),
    "Gaming":          ("applications-games", "\U0001f3ae", "#a06bf0"),
    "Rendimiento":     ("utilities-system-monitor", "\u26a1", "#f0a83c"),
    "Gráficos NVIDIA": ("video-display", "\U0001f5a5", "#3dbb76"),
    "Hardware ASUS":   ("computer", "\U0001f4bb", "#e05a8a"),
    "Terminal":        ("utilities-terminal", "\u276f", "#39b8c0"),
}

# Los colores base salen de la paleta del tema (Plasma claro u oscuro).
STYLE = """
QWidget { font-size: 10.5pt; }

/* ---------- barra lateral ---------- */
QFrame#sidebar { background: palette(window); border-right: 1px solid palette(mid); }
QLabel#brand { font-size: 15pt; font-weight: 700; }
QLabel#brandsub { color: gray; font-size: 9pt; }
QLineEdit#buscar { min-height: 34px; border-radius: 10px; padding: 0 12px;
                   border: 1px solid palette(mid); background: palette(base); }
QLineEdit#buscar:focus { border: 2px solid palette(highlight); }
QListWidget#secciones { background: transparent; border: none; outline: 0; }
QListWidget#secciones::item { padding: 9px 10px; border-radius: 10px; margin: 2px 0; }
QListWidget#secciones::item:hover { background: palette(alternate-base); }
QListWidget#secciones::item:selected { background: palette(highlight);
                                        color: palette(highlighted-text); font-weight: 600; }
QLabel#pagetitle { font-size: 21pt; font-weight: 700; }
QLabel#pagesub { color: gray; font-size: 10.5pt; }
QLabel#pie { color: gray; font-size: 9pt; }

/* ---------- tarjetas ---------- */
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QFrame#tarjeta { background: palette(base); border: 1px solid palette(mid);
                 border-radius: 16px; }
QFrame#tarjeta:hover { border: 1px solid palette(highlight); }
QLabel#nombre { font-size: 12.5pt; font-weight: 700; }
QLabel#detalle { color: gray; font-size: 10pt; }
QLabel#chip { font-size: 9pt; font-weight: 600; border-radius: 9px; padding: 3px 10px; }
QLabel#chip[estado="off"]   { color: #8b949e; background: rgba(139,148,158,0.15); }
QLabel#chip[estado="run"]   { color: #4f9cf0; background: rgba(79,156,240,0.18); }
QLabel#chip[estado="ok"]    { color: #2ea043; background: rgba(46,160,67,0.18); }
QLabel#chip[estado="error"] { color: #d64545; background: rgba(214,69,69,0.18); }

/* ---------- botones ---------- */
QPushButton { min-width: 118px; min-height: 38px; padding: 0 16px;
              border-radius: 10px; font-size: 11pt; font-weight: 600;
              border: 2px solid transparent; }
QPushButton#primario { background: palette(highlight); color: palette(highlighted-text);
                       border-radius: 11px; }
QPushButton#primario:hover { border-color: palette(highlighted-text); }
QPushButton#primario:pressed { background: palette(dark); }
QPushButton#quitar { background: transparent; color: #d64545; border: 2px solid #d64545;
                     border-radius: 11px; }
QPushButton#quitar:hover { background: #d64545; color: white; }
QPushButton#quitar:disabled { color: palette(mid); border-color: palette(mid); }
QPushButton#secundario { background: transparent; color: palette(text);
              border-color: palette(mid); }
QPushButton#secundario:hover { border-color: palette(highlight); }
QPushButton#secundario:disabled { color: palette(mid); }

/* ---------- vista de ejecución ---------- */
QLabel#accion { font-size: 16pt; font-weight: 700; }
QLabel#estado { font-size: 11pt; font-weight: 600; }
QLabel#estado[estado="run"] { color: palette(highlight); }
QLabel#estado[estado="ok"] { color: #2ea043; }
QLabel#estado[estado="error"] { color: #d64545; }
QPlainTextEdit#log { background: #14181c; color: #d7dde2;
                     border: 1px solid palette(mid); border-radius: 12px;
                     padding: 10px; selection-background-color: palette(highlight); }
QLineEdit#entrada { min-height: 34px; padding: 0 12px; border-radius: 10px;
                    border: 2px solid palette(mid); background: palette(base); }
QLineEdit#entrada[atencion="true"] { border-color: palette(highlight); }
"""

# Script de bash fijo: recibe DIR, URL y SCRIPT como $1, $2 y $3 (sin
# interpolar nada en el texto, para evitar problemas de quoting).
PREPARAR = r'''
d=$1; url=$2; s=$3
if [ -d "$d/.git" ]; then
    git -C "$d" pull --ff-only || echo "AVISO: no se pudo actualizar; se usa la copia local."
else
    mkdir -p "$(dirname "$d")" && git clone "$url" "$d" || { echo "ERROR: no se pudo clonar $url"; exit 1; }
fi
[ -f "$d/$s" ] || { echo "ERROR: no existe $s en $d"; exit 1; }
'''

# Igual que el original: se usa cuando hay que abrir el script en Konsole.
BASH_RUNNER = PREPARAR + r'''
bash "$d/$s"; rc=$?
echo; echo "El script terminó con código $rc."
echo; read -rp "Pulsa Enter para cerrar..." _
'''

# Cuadros de diálogo que el whiptail de texto NO sabe convertir: esos scripts
# se abren en Konsole (donde el whiptail real funciona).
DIALOG_RE = re.compile(r"\bdialog\s+--")
TIPOS_NO_SOPORTADOS_RE = re.compile(
    r"--(menu|checklist|radiolist|inputbox|passwordbox|gauge|textbox|tailbox|fselect)\b")

SHIM_DIR = Path.home() / ".local/share/panel-de-configuracion/shims"

# whiptail en modo texto. El lanzador lo pone al principio del PATH solo para
# los scripts que ejecuta dentro de su ventana. Lee y escribe en /dev/tty (el
# pseudo-terminal de la ventana), así que funciona aunque el script redirija
# stdout/stderr. Códigos de salida como whiptail: 0 = sí/aceptar, 1 = no;
# 2 = error del propio shim (uso no soportado / sin /dev/tty), para no
# confundirlo con el 255 (ESC) de whiptail.
SHIM_WHIPTAIL = r'''#!/usr/bin/env bash
# whiptail en modo texto (generado por el lanzador; no editar).
title=""; kind=""; texto=""; yes_lbl="Sí"; no_lbl="No"; defaultno=0
while [ $# -gt 0 ]; do
    case "$1" in
        --title)      title=$2; shift 2 ;;
        --yes-button) yes_lbl=$2; shift 2 ;;
        --no-button)  no_lbl=$2; shift 2 ;;
        --backtitle|--ok-button|--cancel-button) shift 2 ;;
        --defaultno)  defaultno=1; shift ;;
        --yesno|--msgbox|--infobox) kind=${1#--}; texto=$2; shift 2 ;;
        --clear|--nocancel|--scrolltext|--fb|--fullbuttons|--notags|--separate-output) shift ;;
        --*) echo "whiptail (modo texto): opción no soportada: $1" >&2; exit 2 ;;
        *) shift ;;
    esac
done
[ -n "$kind" ] || { echo "whiptail (modo texto): solo admite --yesno, --msgbox e --infobox" >&2; exit 2; }
[ -r /dev/tty ] && [ -w /dev/tty ] || exit 2
{
    printf '\n\033[1;36m━━ %s ━━\033[0m\n' "${title:-Aviso}"
    printf '%b\n' "$texto"
} > /dev/tty
case "$kind" in
    infobox) exit 0 ;;
    msgbox)
        printf 'Pulsa Enter para continuar… ' > /dev/tty
        read -r _ < /dev/tty || exit 2
        exit 0 ;;
esac
if [ "$defaultno" = 1 ]; then hint="s/N"; def=1; else hint="S/n"; def=0; fi
while true; do
    printf 's = %s, n = %s  [%s]: ' "$yes_lbl" "$no_lbl" "$hint" > /dev/tty
    read -r resp < /dev/tty || exit 2
    case "${resp,,}" in
        s|si|sí|y|yes) exit 0 ;;
        n|no)          exit 1 ;;
        "")            exit "$def" ;;
        *) echo "Escribe s o n." > /dev/tty ;;
    esac
done
'''
# Petición de contraseña al final de la línea actual (sudo, ssh, gpg...).
PASS_RE = re.compile(r"(?i)(contraseña|password|passphrase)[^\n]{0,80}:\s*$")

# Secuencias de escape ANSI: CSI, OSC, selección de juego de caracteres y
# escapes de un solo carácter.
ANSI_RE = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]"
    r"|\][^\x07\x1b]*(?:\x07|\x1b\\)"
    r"|[()][0-~]"
    r"|[78=>@-Z\\-_])")

# Paleta legible sobre el fondo oscuro del panel de registro.
FG_DEFECTO = "#d7dde2"
PALETA = ["#8b949e", "#ff6b6b", "#7ee787", "#f2cc60", "#79b8ff", "#d2a8ff",
          "#56d4dd", "#e6edf3",
          "#a0aab4", "#ff8e8e", "#9af5a1", "#ffe08a", "#9dcbff", "#e2c5ff",
          "#7fe9f0", "#ffffff"]


def find_terminal():
    for term in ("konsole", "x-terminal-emulator"):
        if shutil.which(term):
            return term
    return None


def repo_name(url):
    return url.rstrip("/").removesuffix(".git").split("/")[-1]


def datos_seccion(nombre):
    """Icono de tema, emoji de reserva y color de acento de una sección."""
    return SECCIONES.get(nombre, ("application-x-executable", "\u25a3", "#4f9cf0"))


def rgba(hexcolor, alpha):
    """Convierte #RRGGBB a rgba(r,g,b,a); Qt no acepta el formato #RRGGBBAA."""
    c = QColor(hexcolor)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


def entorno():
    """Entorno para los scripts: paginadores no interactivos. NO se fuerza
    TERM=dumb a propósito: hay scripts que interpretan TERM=dumb como "sin
    terminal interactiva" y se saltarían sus propias preguntas (p. ej. el
    setup de gaming). Se respeta el TERM del entorno o, si no hay (o venía en
    "dumb"), se usa uno normal."""
    env = os.environ.copy()
    if not env.get("TERM") or env["TERM"] == "dumb":
        env["TERM"] = "xterm"
    env.update({"PAGER": "cat", "GIT_PAGER": "cat",
                "SYSTEMD_PAGER": "", "LANZADOR_INTEGRADO": "1"})
    try:
        SHIM_DIR.mkdir(parents=True, exist_ok=True)
        ruta = SHIM_DIR / "whiptail"
        if not ruta.exists() or ruta.read_text(encoding="utf-8") != SHIM_WHIPTAIL:
            ruta.write_text(SHIM_WHIPTAIL, encoding="utf-8")
        ruta.chmod(0o755)
        env["PATH"] = f"{SHIM_DIR}:{env.get('PATH', '')}"
    except OSError:
        pass  # sin shim: los scripts con whiptail necesitarán Konsole
    return env


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class PtyRunner(QObject):
    """Ejecuta un proceso dentro de un pseudo-terminal.

    Con un terminal de verdad sudo, read y compañía se comportan igual que en
    Konsole (incluida la caché de credenciales de sudo), pero la salida y la
    entrada pasan por esta ventana en lugar de por otra aplicación.
    """
    salida = pyqtSignal(bytes)
    terminado = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proc = None
        self.master = None
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._tick)

    def activo(self):
        return self.proc is not None

    def start(self, args, env, cwd=None):
        master, slave = pty.openpty()
        # Sin conversión \n -> \r\n: los \r que lleguen serán reales
        # (barras de progreso de git, por ejemplo).
        attrs = termios.tcgetattr(slave)
        attrs[1] &= ~termios.ONLCR
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))

        def hijo():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        try:
            self.proc = subprocess.Popen(args, stdin=slave, stdout=slave,
                                         stderr=slave, preexec_fn=hijo, env=env,
                                         cwd=cwd)
        except OSError:
            try:
                os.close(slave)
            except OSError:
                pass
            try:
                os.close(master)
            except OSError:
                pass
            raise
        os.close(slave)
        os.set_blocking(master, False)
        self.master = master
        self.timer.start()

    def enviar(self, texto):
        if self.master is None:
            return
        try:
            os.write(self.master, (texto + "\n").encode())
        except OSError:
            pass

    def cancelar(self):
        """Ctrl+C en el terminal; si el script no hace caso, TERM y luego KILL."""
        if not self.activo():
            return
        try:
            os.write(self.master, b"\x03")
        except OSError:
            pass
        QTimer.singleShot(4000, lambda p=self.proc: self._escalar(p, signal.SIGTERM))
        QTimer.singleShot(8000, lambda p=self.proc: self._escalar(p, signal.SIGKILL))

    def matar(self):
        if self.activo():
            self._escalar(self.proc, signal.SIGKILL)

    def _escalar(self, proc, sig):
        if proc is self.proc and proc.poll() is None:
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                pass

    def _leer(self):
        while True:
            try:
                listo, _, _ = select.select([self.master], [], [], 0)
                if not listo:
                    return
                datos = os.read(self.master, 65536)
            except OSError:
                return
            if not datos:
                return
            self.salida.emit(datos)

    def _tick(self):
        self._leer()
        rc = self.proc.poll()
        if rc is None:
            return
        self._leer()  # lo último que quedara en el búfer
        self.timer.stop()
        try:
            os.close(self.master)
        except OSError:
            pass
        self.master = None
        self.proc = None
        self.terminado.emit(rc)


class VistaLog(QPlainTextEdit):
    """Panel de registro tipo terminal: interpreta colores ANSI y \\r."""

    def __init__(self):
        super().__init__()
        self.setObjectName("log")
        self.setReadOnly(True)
        self.setMaximumBlockCount(20000)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.limpiar()

    def limpiar(self):
        self.clear()
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._resto = ""       # secuencia de escape cortada entre dos lecturas
        self._cr = False       # \r pendiente de saber si va seguido de \n
        self._fmt = self._formato_base()

    @staticmethod
    def _formato_base():
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(FG_DEFECTO))
        return fmt

    def _al_final(self):
        sb = self.verticalScrollBar()
        return sb.value() >= sb.maximum() - 4

    def _bajar(self):
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def feed(self, datos):
        texto = self._resto + self._decoder.decode(datos)
        self._resto = ""
        i = texto.rfind("\x1b")
        if i != -1 and not ANSI_RE.match(texto, i) and len(texto) - i < 64:
            self._resto = texto[i:]
            texto = texto[:i]
        seguir = self._al_final()
        pos = 0
        for m in ANSI_RE.finditer(texto):
            self._texto(texto[pos:m.start()])
            seq = m.group(0)
            if seq.startswith("\x1b[") and seq.endswith("m"):
                self._sgr(seq[2:-1])
            pos = m.end()
        self._texto(texto[pos:])
        if seguir:
            self._bajar()

    def sistema(self, mensaje, color="#56d4dd"):
        """Línea propia del lanzador (no del script), en negrita y color."""
        seguir = self._al_final()
        cur = self.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        if self.document().lastBlock().text():
            cur.insertBlock()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        fmt.setFontWeight(700)
        cur.insertText(mensaje, fmt)
        cur.insertBlock()
        if seguir:
            self._bajar()

    def ultima_linea(self):
        return self.document().lastBlock().text()

    def _texto(self, s):
        if not s:
            return
        if self._cr:
            self._cr = False
            if not s.startswith("\n"):
                s = "\r" + s
        if s.endswith("\r"):
            self._cr = True
            s = s[:-1]
        cur = self.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        for parte in re.split(r"(\r\n|\n|\r)", s):
            if not parte:
                continue
            if parte in ("\n", "\r\n"):
                cur.insertBlock()
            elif parte == "\r":
                # Vuelta al inicio de línea: lo siguiente reescribe la línea.
                cur.movePosition(QTextCursor.MoveOperation.StartOfBlock,
                                 QTextCursor.MoveMode.KeepAnchor)
                cur.removeSelectedText()
            else:
                cur.insertText(parte, self._fmt)

    def _sgr(self, params):
        nums = [int(p) if p.isdigit() else 0 for p in params.split(";")] if params else [0]
        i = 0
        while i < len(nums):
            n = nums[i]
            if n == 0:
                self._fmt = self._formato_base()
            elif n == 1:
                self._fmt.setFontWeight(700)
            elif n == 22:
                self._fmt.setFontWeight(400)
            elif 30 <= n <= 37:
                self._fmt.setForeground(QColor(PALETA[n - 30]))
            elif 90 <= n <= 97:
                self._fmt.setForeground(QColor(PALETA[n - 90 + 8]))
            elif n == 39:
                self._fmt.setForeground(QColor(FG_DEFECTO))
            elif n in (38, 48):
                modo = nums[i + 1] if i + 1 < len(nums) else 0
                if modo == 2:
                    if n == 38 and i + 4 < len(nums):
                        self._fmt.setForeground(QColor(nums[i + 2], nums[i + 3], nums[i + 4]))
                    i += 4
                elif modo == 5:
                    i += 2
            i += 1


class TarjetaAccion(QFrame):
    """Tarjeta de una acción: icono, título, descripción, chip de estado y
    botón. El botón llama al lanzador con su acción; el chip lo actualiza el
    lanzador mientras la acción se ejecuta."""

    def __init__(self, item, on_run):
        super().__init__()
        self.item = item
        self.setObjectName("tarjeta")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        tema, emoji, color = datos_seccion(item["seccion"])
        sombra = QGraphicsDropShadowEffect(self)
        sombra.setBlurRadius(26)
        sombra.setOffset(0, 6)
        sombra.setColor(QColor(0, 0, 0, 45))
        self.setGraphicsEffect(sombra)

        col = QVBoxLayout(self)
        col.setContentsMargins(20, 18, 20, 18)
        col.setSpacing(12)

        cab = QHBoxLayout()
        cab.setSpacing(12)
        icono = QLabel()
        icono.setFixedSize(50, 50)
        icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico = QIcon.fromTheme(tema)
        estilo = f"background: {rgba(color, 0.14)}; border-radius: 13px;"
        if ico.isNull():
            icono.setText(emoji)
            estilo += f" color: {color}; font-size: 20pt;"
        else:
            icono.setPixmap(ico.pixmap(30, 30))
        icono.setStyleSheet(estilo)
        nombre = QLabel(item["titulo"])
        nombre.setObjectName("nombre")
        nombre.setWordWrap(True)
        cab.addWidget(icono, 0, Qt.AlignmentFlag.AlignTop)
        cab.addWidget(nombre, 1, Qt.AlignmentFlag.AlignVCenter)

        detalle_txt = item.get("descripcion", "")
        if item.get("modo") == "terminal":
            detalle_txt += "  ·  Se abre en Konsole."
        detalle = QLabel(detalle_txt)
        detalle.setObjectName("detalle")
        detalle.setWordWrap(True)

        pie = QHBoxLayout()
        pie.setSpacing(10)
        self.chip = QLabel()
        self.chip.setObjectName("chip")
        self.estado("off", "Sin ejecutar")

        peligroso = bool(item.get("peligroso"))
        boton = QPushButton("\U0001f5d1  Quitar" if peligroso else "\u25b6  Ejecutar")
        boton.setObjectName("quitar" if peligroso else "primario")
        boton.setCursor(Qt.CursorShape.PointingHandCursor)
        boton.clicked.connect(lambda _=False, it=item: on_run(it))
        self.boton = boton

        pie.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignVCenter)
        pie.addStretch(1)
        pie.addWidget(boton, 0, Qt.AlignmentFlag.AlignVCenter)

        col.addLayout(cab)
        if detalle_txt:
            col.addWidget(detalle)
        col.addStretch(1)
        col.addLayout(pie)

    def estado(self, tipo, texto):
        self.chip.setProperty("estado", tipo)
        self.chip.setText(texto)
        repolish(self.chip)


class Launcher(QWidget):
    def __init__(self, config):
        super().__init__()
        self.base = Path(os.path.expanduser(config["carpeta_proyectos"]))
        self.ctx = None
        self.setWindowTitle("Panel de Configuración")
        self.setMinimumSize(840, 620)
        self.resize(1120, 820)

        self.runner = PtyRunner(self)
        self.runner.salida.connect(self._salida)
        self.runner.terminado.connect(self._terminado)
        self.timer_espera = QTimer(self)
        self.timer_espera.setSingleShot(True)
        self.timer_espera.timeout.connect(self._esperando_respuesta)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_home(config))
        self.stack.addWidget(self._build_run())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

    # ---------------------------------------------------------------- inicio

    def _build_home(self, config):
        self.acciones = config["acciones"]
        self.tarjetas = []      # [(item, TarjetaAccion), ...]
        self.visibles = []
        page = QWidget()
        raiz = QHBoxLayout(page)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self._build_sidebar())
        raiz.addWidget(self._build_main(), 1)
        return page

    def _build_sidebar(self):
        barra = QFrame()
        barra.setObjectName("sidebar")
        barra.setFixedWidth(240)
        col = QVBoxLayout(barra)
        col.setContentsMargins(16, 20, 16, 16)
        col.setSpacing(12)

        marca = QLabel("\u25c8  Panel de Configuración")
        marca.setObjectName("brand")
        marca.setWordWrap(True)
        sub = QLabel("Debian Testing")
        sub.setObjectName("brandsub")

        self.buscar = QLineEdit()
        self.buscar.setObjectName("buscar")
        self.buscar.setPlaceholderText("\U0001f50d  Buscar acciones\u2026")
        self.buscar.setClearButtonEnabled(True)
        self.buscar.textChanged.connect(self.aplicar_filtro)

        self.lista = QListWidget()
        self.lista.setObjectName("secciones")
        self.lista.setFrameShape(QFrame.Shape.NoFrame)
        self.lista.addItem(self._item_seccion("Todas", "view-grid", None))
        for nombre in self._orden_secciones():
            tema, emoji, _ = datos_seccion(nombre)
            self.lista.addItem(self._item_seccion(nombre, tema, emoji))
        self.lista.setCurrentRow(0)
        self.lista.currentRowChanged.connect(self.aplicar_filtro)

        pie = QLabel(f"Los proyectos se guardan en {self.base}")
        pie.setObjectName("pie")
        pie.setWordWrap(True)
        pie.setToolTip(str(self.base))

        col.addWidget(marca)
        col.addWidget(sub)
        col.addSpacing(6)
        col.addWidget(self.buscar)
        col.addSpacing(4)
        col.addWidget(self.lista, 1)
        col.addWidget(pie)
        return barra

    @staticmethod
    def _item_seccion(nombre, tema, emoji):
        item = QListWidgetItem(f"  {nombre}")
        # La sección real se guarda aparte del texto visible (que puede llevar
        # icono o emoji), para que el filtro no dependa de ellos.
        item.setData(Qt.ItemDataRole.UserRole, nombre)
        ico = QIcon.fromTheme(tema)
        if ico.isNull() and emoji:
            item.setText(f"  {emoji}  {nombre}")
        else:
            item.setIcon(ico)
        return item

    def _orden_secciones(self):
        orden = []
        for item in self.acciones:
            if item["seccion"] not in orden:
                orden.append(item["seccion"])
        return orden

    def _build_main(self):
        cont = QWidget()
        col = QVBoxLayout(cont)
        col.setContentsMargins(28, 24, 28, 12)
        col.setSpacing(4)

        self.lbl_pagina = QLabel("Todas las acciones")
        self.lbl_pagina.setObjectName("pagetitle")
        self.lbl_sub = QLabel("")
        self.lbl_sub.setObjectName("pagesub")
        col.addWidget(self.lbl_pagina)
        col.addWidget(self.lbl_sub)
        col.addSpacing(12)

        contenedor = QWidget()
        ccol = QVBoxLayout(contenedor)
        ccol.setContentsMargins(0, 0, 8, 20)
        ccol.setSpacing(0)
        self.grid = QGridLayout()
        self.grid.setSpacing(18)
        ccol.addLayout(self.grid)
        self.vacio = QLabel("No hay acciones que coincidan con la búsqueda.")
        self.vacio.setObjectName("pagesub")
        self.vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ccol.addWidget(self.vacio)
        ccol.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(contenedor)
        # El layout puede cambiar de ancho sin que cambie el tamaño de la
        # ventana; escuchamos el viewport para recalcular las columnas.
        scroll.viewport().installEventFilter(self)
        self.scroll = scroll
        col.addWidget(scroll, 1)

        for item in self.acciones:
            self.tarjetas.append((item, TarjetaAccion(item, self.run)))
        self.aplicar_filtro()
        return cont

    def _seccion_actual(self):
        fila = self.lista.currentRow()
        if fila <= 0:
            return None
        return self.lista.item(fila).data(Qt.ItemDataRole.UserRole)

    def aplicar_filtro(self):
        if not hasattr(self, "grid"):
            return
        texto = self.buscar.text().strip().lower()
        seccion = self._seccion_actual()
        visibles = []
        for item, card in self.tarjetas:
            ok_sec = seccion is None or item["seccion"] == seccion
            objetivo = (item["titulo"] + " " +
                        item.get("descripcion", "")).lower()
            ok_txt = not texto or texto in objetivo
            visible = ok_sec and ok_txt
            card.setVisible(visible)
            if visible:
                visibles.append(card)
        self.visibles = visibles
        self.lbl_pagina.setText(seccion or "Todas las acciones")
        n = len(visibles)
        plural = "acción" if n == 1 else "acciones"
        self.lbl_sub.setText(f"{n} {plural} disponibles")
        self.vacio.setVisible(n == 0)
        self._colocar()

    def _colocar(self):
        while self.grid.count():
            self.grid.takeAt(0)
        ancho = self.scroll.viewport().width()
        if ancho < 200:  # antes de que Qt reparta el layout
            ancho = max(200, self.width() - 240 - 60)
        cols = max(1, min(4, (ancho + 18) // (280 + 18)))
        for i, card in enumerate(self.visibles):
            self.grid.addWidget(card, i // cols, i % cols)
        for c in range(4):
            self.grid.setColumnStretch(c, 1 if c < cols else 0)

    def _tarjeta_de(self, item):
        for it, card in self.tarjetas:
            if it is item:
                return card
        return None

    def _marcar(self, item, tipo, texto):
        card = self._tarjeta_de(item)
        if card is not None:
            card.estado(tipo, texto)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "grid"):
            self._colocar()

    def eventFilter(self, obj, event):
        if (hasattr(self, "scroll") and obj is self.scroll.viewport()
                and event.type() == QEvent.Type.Resize and hasattr(self, "grid")):
            self._colocar()
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------- ejecución

    def _build_run(self):
        page = QWidget()
        self.btn_volver = QPushButton("←  Volver")
        self.btn_volver.setObjectName("secundario")
        self.btn_volver.clicked.connect(self.volver)
        self.lbl_accion = QLabel()
        self.lbl_accion.setObjectName("accion")
        self.lbl_estado = QLabel()
        self.lbl_estado.setObjectName("estado")

        cab = QHBoxLayout()
        cab.setSpacing(14)
        cab.addWidget(self.btn_volver)
        cab.addWidget(self.lbl_accion, 1)
        cab.addWidget(self.lbl_estado)

        self.log = VistaLog()

        self.entrada = QLineEdit()
        self.entrada.setObjectName("entrada")
        self.entrada.returnPressed.connect(self.enviar)
        self.btn_enviar = QPushButton("Enviar")
        self.btn_enviar.setObjectName("primario")
        self.btn_enviar.clicked.connect(self.enviar)
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("quitar")
        self.btn_cancelar.clicked.connect(self.cancelar)

        fila = QHBoxLayout()
        fila.setSpacing(12)
        fila.addWidget(self.entrada, 1)
        fila.addWidget(self.btn_enviar)
        fila.addWidget(self.btn_cancelar)

        ayuda = QLabel("Si el script hace una pregunta o pide tu contraseña de "
                       "sudo, escríbela arriba y pulsa Enter.")
        ayuda.setObjectName("pie")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 30, 36, 22)
        layout.setSpacing(14)
        layout.addLayout(cab)
        layout.addWidget(self.log, 1)
        layout.addLayout(fila)
        layout.addWidget(ayuda)
        return page

    def run(self, item):
        if self.runner.activo():
            return
        if item.get("peligroso"):
            answer = QMessageBox.question(
                self, "Confirmar",
                f"«{item['titulo']}» puede eliminar paquetes y archivos.\n\n"
                "¿Ejecutarlo?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        modo = item.get("modo", "auto")
        if modo not in MODOS:
            modo = "auto"
        if modo == "terminal":
            ok = self.abrir_terminal(item)
            self._marcar(item, "ok" if ok else "error",
                         "Abierto en Konsole" if ok else "Error")
            return
        self.iniciar(item, modo)

    def abrir_terminal(self, item):
        terminal = find_terminal()
        if terminal is None:
            QMessageBox.critical(self, "Sin terminal",
                                 "No se encontró konsole ni x-terminal-emulator.")
            return False
        dest = self.base / repo_name(item["repo"])
        subprocess.Popen(
            [terminal, "-e", "bash", "-c", BASH_RUNNER, "_",
             str(dest), item["repo"], item["script"]],
            start_new_session=True)
        return True

    def iniciar(self, item, modo):
        dest = self.base / repo_name(item["repo"])
        self.ctx = {"item": item, "modo": modo, "dest": dest,
                    "fase": "preparar", "cancelado": False}
        self.log.limpiar()
        self.lbl_accion.setText(item["titulo"])
        self._estado("run", "En ejecución…")
        self._marcar(item, "run", "En ejecución…")
        self._controles(True)
        self._ir_a(1)
        self.log.sistema("▶ Preparando el proyecto (git)…")
        try:
            self.runner.start(["bash", "-c", PREPARAR, "_", str(dest),
                               item["repo"], item["script"]], entorno())
        except OSError as err:
            self._fin(f"No se pudo iniciar el proceso: {err}", "✖ Falló")

    def _terminado(self, rc):
        ctx = self.ctx
        if ctx is None:
            return
        if ctx["cancelado"]:
            self._fin("Cancelado por el usuario.", "Cancelado")
            return
        if ctx["fase"] == "preparar":
            if rc != 0:
                self._fin("No se pudo preparar el proyecto.", f"Falló (código {rc})")
                return
            # Sincronización opcional de los índices de APT antes del script
            # (campo "apt_update": true en proyectos.json). Se ejecuta en el
            # mismo PTY, así la contraseña de sudo se pide en la ventana y su
            # caché queda caliente para el script.
            if ctx["item"].get("apt_update"):
                ctx["fase"] = "apt"
                self.log.sistema("▶ Sincronizando índices de APT (sudo apt update)…")
                try:
                    self.runner.start(["sudo", "apt", "update"], entorno(),
                                      cwd=str(Path.home()))
                except OSError as err:
                    self._fin(f"No se pudo iniciar 'apt update': {err}", "✖ Falló")
                return
            self._arrancar_script(ctx)
            return
        if ctx["fase"] == "apt":
            # Un fallo de apt update (p. ej. sin red) no aborta: se avisa y se
            # sigue con el script, que puede funcionar igualmente.
            if rc != 0:
                self.log.sistema("'apt update' falló; se continúa con el script.",
                                 color="#f2cc60")
            self._arrancar_script(ctx)
            return
        if rc == 0:
            self._fin("El script terminó correctamente.", "✔ Completado", ok=True)
        else:
            self._fin(f"El script terminó con código {rc}.", f"✖ Falló (código {rc})")

    def _arrancar_script(self, ctx):
        script = ctx["dest"] / ctx["item"]["script"]
        try:
            contenido = script.read_text(encoding="utf-8", errors="replace")
        except OSError:
            contenido = ""
        # Se ignoran las líneas de comentario para no confundir una mera
        # mención (p. ej. "--menu" en un comentario) con un uso real.
        codigo = "\n".join(
            l for l in contenido.splitlines() if not l.lstrip().startswith("#"))
        usa_dialogos = bool(DIALOG_RE.search(codigo)) or (
            "whiptail" in codigo and bool(TIPOS_NO_SOPORTADOS_RE.search(codigo)))
        if ctx["modo"] == "auto" and usa_dialogos:
            self.log.sistema("Este script usa menús, listas o campos de "
                             "texto (whiptail/dialog) que no se pueden "
                             "mostrar aquí: se abre en Konsole.")
            if self.abrir_terminal(ctx["item"]):
                self._fin("Abierto en Konsole.", "Abierto en Konsole", ok=True)
            else:
                self._fin("No hay ninguna terminal disponible.", "Falló")
            return
        if ctx["modo"] == "gui":
            self._lanzar_gui(script)
            return
        ctx["fase"] = "ejecutar"
        self.log.sistema("▶ Ejecutando el script…")
        try:
            self.runner.start(["bash", str(script)], entorno(),
                              cwd=str(Path.home()))
        except OSError as err:
            self._fin(f"No se pudo iniciar el script: {err}", "✖ Falló")

    def _lanzar_gui(self, script):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ruta = LOG_DIR / f"{script.stem}.log"
        try:
            with open(ruta, "wb") as salida:
                proc = subprocess.Popen(
                    ["bash", str(script)], stdin=subprocess.DEVNULL,
                    stdout=salida, stderr=subprocess.STDOUT,
                    start_new_session=True, cwd=str(Path.home()))
        except OSError as err:
            self._fin(f"No se pudo iniciar: {err}", "✖ Falló")
            return
        self.ctx.update(fase="gui", proc_gui=proc, log_gui=ruta)
        self.log.sistema("▶ Abriendo la aplicación (sin terminal)…")
        QTimer.singleShot(3000, self._comprobar_gui)

    def _comprobar_gui(self):
        ctx = self.ctx
        if ctx is None or ctx.get("fase") != "gui":
            return
        rc = ctx["proc_gui"].poll()
        if rc is None:
            self._fin("El script de la aplicación sigue ejecutándose; se asume "
                      "que la aplicación está arrancando. Puedes cerrar esta vista.",
                      "✔ Lanzada", ok=True)
            return
        if rc == 0:
            self._fin("El script de la aplicación terminó correctamente.",
                      "✔ Completada", ok=True)
            return
        try:
            cola = ctx["log_gui"].read_text(encoding="utf-8", errors="replace")[-3000:]
        except OSError:
            cola = ""
        if cola:
            self.log.sistema("Salida del script:", color="#f2cc60")
            self.log.feed(cola.encode())
        self._fin(f"La aplicación terminó con código {rc}.", f"✖ Falló (código {rc})")

    def _fin(self, mensaje, estado, ok=False):
        item = self.ctx.get("item") if self.ctx else None
        self.log.sistema(mensaje, color="#7ee787" if ok else "#ff6b6b")
        self._estado("ok" if ok else "error", estado)
        if item is not None:
            tipo = "ok" if ok else ("off" if estado == "Cancelado" else "error")
            self._marcar(item, tipo, estado)
        self._controles(False)
        self.timer_espera.stop()
        self.ctx = None

    def _estado(self, tipo, texto):
        self.lbl_estado.setText(texto)
        self.lbl_estado.setProperty("estado", tipo)
        repolish(self.lbl_estado)

    def _controles(self, ejecutando):
        self.btn_volver.setEnabled(not ejecutando)
        self.entrada.setEnabled(ejecutando)
        self.btn_enviar.setEnabled(ejecutando)
        self.btn_cancelar.setEnabled(ejecutando)
        self.entrada.clear()
        self.entrada.setEchoMode(QLineEdit.EchoMode.Normal)
        self.entrada.setPlaceholderText("Respuesta al script…" if ejecutando else "")
        self._atencion(False)
        if ejecutando:
            self.entrada.setFocus()

    def _atencion(self, activa):
        self.entrada.setProperty("atencion", "true" if activa else "false")
        repolish(self.entrada)

    # ------------------------------------------------------- entrada / salida

    def _salida(self, datos):
        self.log.feed(datos)
        linea = self.log.ultima_linea()
        # "?" descarta preguntas que solo mencionan la palabra (p. ej.
        # "¿Guardar contraseña:"), que no son una petición real de clave.
        pide_clave = "?" not in linea and bool(PASS_RE.search(linea))
        modo = QLineEdit.EchoMode.Password if pide_clave else QLineEdit.EchoMode.Normal
        if self.entrada.echoMode() != modo:
            self.entrada.setEchoMode(modo)
            self.entrada.setPlaceholderText(
                "Contraseña (no se muestra)…" if pide_clave else "Respuesta al script…")
        self._atencion(False)
        self.timer_espera.start(700)

    def _esperando_respuesta(self):
        """Salida parada con una línea a medias: casi seguro es una pregunta."""
        if self.runner.activo() and self.log.ultima_linea():
            self._atencion(True)
            self.entrada.setFocus()

    def enviar(self):
        if not self.runner.activo():
            return
        texto = self.entrada.text()
        self.entrada.clear()
        self._atencion(False)
        self.runner.enviar(texto)

    def cancelar(self):
        if self.runner.activo() and self.ctx is not None:
            self.ctx["cancelado"] = True
            self.log.sistema("Cancelando…", color="#f2cc60")
            self.runner.cancelar()

    def volver(self):
        self._ir_a(0)

    def _ir_a(self, indice):
        """Cambia de página con un fundido corto. El efecto de opacidad se
        quita al terminar para que las sombras de las tarjetas vuelvan a
        dibujarse (Qt no anida efectos gráficos)."""
        self.stack.setCurrentIndex(indice)
        pagina = self.stack.currentWidget()
        efecto = QGraphicsOpacityEffect(pagina)
        pagina.setGraphicsEffect(efecto)
        anim = QPropertyAnimation(efecto, b"opacity", self)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: pagina.setGraphicsEffect(None))
        self._anim = anim  # mantener referencia mientras corre
        anim.start()

    def closeEvent(self, event):
        if self.runner.activo():
            answer = QMessageBox.question(
                self, "Salir", "Hay un script en ejecución. ¿Cancelarlo y salir?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.runner.matar()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    if os.geteuid() == 0:
        QMessageBox.critical(None, "No como root",
                             "Ejecuta el lanzador como usuario normal; "
                             "los scripts piden sudo por sí mismos.")
        return 1
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        window = Launcher(config)
    except (OSError, ValueError, KeyError, TypeError) as err:
        QMessageBox.critical(None, "Error de configuración",
                             f"No se pudo leer {CONFIG}:\n{err}")
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
