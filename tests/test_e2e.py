"""De punta a punta: un cliente de tmux real en un terminal virtual (pty) que
pulsa teclas como lo harías tú. Cubre el popup del selector, fzf y el ciclo de
las ventanas flotantes, que las demás pruebas no pueden ver."""
import os
import pty
import select
import shutil
import struct
import threading
import time
import unittest

try:
    import fcntl
    import termios
except ImportError:  # pragma: no cover
    fcntl = termios = None

from escenario import CasoMundo
from mundo import RAIZ

PREFIJO = b"\x02"  # C-b, el de tmux sin configurar


@unittest.skipUnless(shutil.which("tmux") and shutil.which("fzf") and termios, "hace falta tmux, fzf y pty")
class E2E(CasoMundo):
    def setUp(self):
        super().setUp()
        m = self.m
        flotante = m.dir / "abrir-flotante.sh"
        flotante.write_text('#!/bin/sh\nexec tmux display-popup -c "$2" -w 80% -h 80% -E "tmux new-session -A -s f-$1"\n')
        flotante.chmod(0o755)
        conf = m.dir / "tmux.conf"
        conf.write_text(
            f"set -g @ws-bin '{m.bin / 'ws'}'\n"
            f"set -g @ws-float-script '{flotante}'\n"
            "set -g escape-time 0\n"
            f"run-shell '{RAIZ / 'ws.tmux'}'\n"
            "bind-key -n M-g if-shell -F '#{m:f-*,#{session_name}}' "
            "{ run-shell 'tmux set -t \"=#{s/^f-//:session_name}:\" @float_abierta 0' ; detach-client } "
            f"{{ run-shell -b '{flotante} #{{session_name}} #{{client_name}}' }}\n")
        m.socket = m.socket_corto()
        env = m.env()
        env.pop("TMUX")
        env["TERM"] = "xterm-256color"
        import subprocess
        subprocess.run(["tmux", "-S", m.socket, "-f", str(conf), "new-session", "-d", "-s", "_base",
                        "-x", "160", "-y", "45", "-c", str(m.home)], check=True, env=env)
        # cliente real
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.execvpe("tmux", ["tmux", "-S", m.socket, "attach", "-t", "_base"], env)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", 45, 160, 0, 0))
        self._vivo = True
        threading.Thread(target=self._drenar, daemon=True).start()
        self.esperar(lambda: self.cliente_en() == "_base", "el cliente no se enganchó")

    def tearDown(self):
        self._vivo = False
        try:
            os.kill(self.pid, 9)
            os.waitpid(self.pid, 0)
        except OSError:
            pass
        super().tearDown()

    # ─── utilidades ──────────────────────────────────────────────────────────

    def _drenar(self):
        while self._vivo:
            try:
                r, _, _ = select.select([self.fd], [], [], 0.1)
                if r:
                    os.read(self.fd, 65536)
            except OSError:
                return

    def teclas(self, *trozos, pausa=0.25):
        for t in trozos:
            os.write(self.fd, t if isinstance(t, bytes) else t.encode())
            time.sleep(pausa)

    def esperar(self, cond, mensaje, timeout=10):
        fin = time.time() + timeout
        while time.time() < fin:
            if cond():
                return
            time.sleep(0.1)
        self.fail(mensaje)

    def clientes(self):
        salida = self.m.tmux("list-clients", "-F", "#{client_name} #{session_name}")
        return dict(l.split(" ", 1) for l in salida.splitlines() if " " in l)

    def cliente_en(self):
        """Sesión del cliente exterior (el del pty, que no está en una flotante)."""
        for _, sesion in self.clientes().items():
            if not sesion.startswith("f-"):
                return sesion
        return None

    def fzf_abierto(self, texto=None):
        return any(texto is None or texto in a for a in self.m.listas_fzf())

    def abrir_selector(self):
        self.teclas(PREFIJO, "s", pausa=0.1)
        self.esperar(self.fzf_abierto, "no se abrió el selector")
        time.sleep(0.3)  # fzf ya está en marcha; margen para que lea el terminal

    def elegir(self, busqueda):
        """prefix+s, buscar y Enter, como lo harías tú."""
        self.abrir_selector()
        self.teclas("/", busqueda, pausa=0.4)
        self.teclas("\r", pausa=0.1)
        self.esperar(lambda: not self.fzf_abierto(), "el selector no se cerró")

    # ─── pruebas ─────────────────────────────────────────────────────────────

    def test_selector_abre_un_proyecto(self):
        self.elegir("crm")
        self.esperar(lambda: self.cliente_en() == "au-crm", f"no saltó a au-crm: {self.clientes()}")
        self.assertEqual(self.m.tmux("show", "-t", "=au-crm:", "-qv", "@ws"), "aura/crm")

    def test_esc_cierra_sin_tocar_nada(self):
        self.abrir_selector()
        self.teclas("\x1b", pausa=0.1)
        self.esperar(lambda: not self.fzf_abierto(), "Esc no cerró el selector")
        self.assertEqual(self.cliente_en(), "_base")

    def test_ciclo_de_flotante(self):
        # 1. abrir la flotante de _base
        self.teclas("\x1bg", pausa=0.8)
        self.esperar(lambda: "f-_base" in self.clientes().values(), "no se abrió la flotante")
        # 2. prefix+s DESDE la flotante y cancelar: la flotante vuelve
        self.abrir_selector()
        self.esperar(lambda: "f-_base" not in self.clientes().values(), "la flotante no se cerró sola")
        self.teclas("\x1b", pausa=0.1)
        self.esperar(lambda: "f-_base" in self.clientes().values(), "no volvió la flotante al cancelar")
        # 3. desde la flotante, ir a otro proyecto: la flotante se queda apuntada en _base
        self.elegir("crm")
        self.esperar(lambda: self.cliente_en() == "au-crm", f"no saltó: {self.clientes()}")
        self.assertNotIn("f-au-crm", self.clientes().values())
        self.assertEqual(self.m.tmux("show", "-t", "=_base:", "-qv", "@float_abierta"), "1")
        # 4. volver a _base: su flotante se reabre sola
        self.elegir("_base")
        self.esperar(lambda: "f-_base" in self.clientes().values(), f"no se reabrió la flotante: {self.clientes()}")


if __name__ == "__main__":
    unittest.main()

