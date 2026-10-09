"""De punta a punta: confirmaciones con «Sí» primero y respuesta de una tecla."""
import shutil
import time
import unittest

import test_e2e
from test_e2e import PREFIJO, termios


@unittest.skipUnless(shutil.which("tmux") and shutil.which("fzf") and termios, "hace falta tmux, fzf y pty")
class Confirmar(test_e2e.E2E):
    """^x sobre una sesión: «Sí» va primero y basta una tecla."""

    def cerrar(self, tecla):
        nombre = f"zz-{id(self) % 100000}"
        self.m.tmux("new-session", "-d", "-s", nombre, "-c", str(self.m.home))
        self.abrir_selector()
        self.teclas("/", nombre, pausa=0.4)               # filtrar: queda elegida
        self.teclas("\x18", pausa=0.1)                    # ^x
        self.esperar(lambda: self.fzf_abierto(nombre), "no salió la confirmación")
        time.sleep(0.3)
        self.teclas(tecla, pausa=0.1)
        self.esperar(lambda: not self.fzf_abierto(nombre), "la confirmación no se cerró")
        self.teclas("\x1b", "\x1b", pausa=0.3)            # salir de la búsqueda y del selector
        return nombre in self.m.tmux("list-sessions", "-F", "#{session_name}").split()

    def test_enter_confirma_porque_si_va_primero(self):
        self.assertFalse(self.cerrar("\r"))

    def test_y_confirma_sin_moverse(self):
        self.assertFalse(self.cerrar("y"))

    def test_n_cancela(self):
        self.assertTrue(self.cerrar("n"))

    def test_en_espanol_s_confirma(self):
        self.m.tmux("set", "-g", "@ws-lang", "es")
        self.assertFalse(self.cerrar("s"))

    # el ciclo completo ya lo cubre test_e2e; aquí no se repite
    test_selector_abre_un_proyecto = test_esc_cierra_sin_tocar_nada = test_ciclo_de_flotante = None


if __name__ == "__main__":
    unittest.main()
