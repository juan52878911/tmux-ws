"""Integración con tmux (servidor propio por prueba) y la lógica del selector."""
import json
import os
import subprocess
import sys
import unittest

from escenario import CasoMundo
from mundo import RAIZ, WS_PY


class Tmux(CasoMundo):
    def setUp(self):
        super().setUp()
        self.m.tmux_iniciar()

    def marca(self, sesion):
        return self.m.tmux("show", "-t", f"={sesion}:", "-qv", "@ws")

    def test_apply_marca_por_carpeta_inicial(self):
        self.m.sesion("api", self.m.ruta("empresa/api"))
        self.m.sesion("libre", self.m.home)
        for s in ("api", "libre"):
            self.ws_ok("apply", s)
        self.assertEqual(self.marca("api"), "empresa/api")
        self.assertEqual(self.marca("libre"), "")

    def test_flotante_hereda_y_prefijo_configurable(self):
        self.m.sesion("api", self.m.ruta("empresa/api"), marca="empresa/api")
        self.m.tmux("set", "-g", "@ws-float-prefix", "pop_")
        self.m.sesion("pop_api", self.m.home)
        self.ws_ok("apply", "pop_api")
        self.assertEqual(self.marca("pop_api"), "empresa/api")

    def test_fuera_de_carpeta_la_sesion_aporta_solo_la_org(self):
        pane = self.m.sesion("p", self.m.home, marca="empresa/propio")
        r = self.ws_ok("contexto", "--json", cwd=self.m.home, TMUX_PANE=pane)
        c = json.loads(r.stdout)
        # empresa/propio usa claude personal; fuera de su carpeta manda la org (propia)
        self.assertEqual((c["grupo"], c["proyecto"], c["origen"]), ("empresa", None, "tmux"))
        self.m.run(["claude"], cwd=self.m.home, TMUX_PANE=pane)
        self.assertEqual(self.m.ultima("claude")["env"]["CLAUDE_CONFIG_DIR"],
                         str(self.m.estado("claude", "empresa")))

    def test_descubrir_remarca_sesion_y_flotante(self):
        pane = self.m.sesion("trabajo", self.m.home, marca="empresa")
        self.m.sesion("f-trabajo", self.m.home, marca="empresa")
        ruta = self.m.repo(self.m.home / "src/nuevo", "https://github.com/empresa-co/nuevo")
        self.ws_ok("descubrir", str(ruta), TMUX_PANE=pane)
        self.assertEqual(self.marca("trabajo"), "empresa/nuevo")
        self.assertEqual(self.marca("f-trabajo"), "empresa/nuevo")

    def test_no_remarca_sesion_de_otro_grupo(self):
        pane = self.m.sesion("aura", self.m.ruta("aura/crm"), marca="aura/crm")
        ruta = self.m.repo(self.m.home / "src/nuevo2", "https://github.com/empresa-co/nuevo2")
        self.ws_ok("descubrir", str(ruta), TMUX_PANE=pane)
        self.assertEqual(self.marca("aura"), "aura/crm")


class Selector(CasoMundo):
    """La lógica de ws_menu, sin popup: filas, vista previa, abrir, acciones."""

    def setUp(self):
        super().setUp()
        self.m.tmux_iniciar()

    def py(self, codigo, **env):
        pre = f"import sys; sys.path.insert(0, {str(RAIZ / 'src')!r}); import ws, ws_menu as m\n"
        r = self.m.run([sys.executable, "-c", pre + codigo], **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def filas(self):
        return [l.split("\t")[0] for l in self.ws_ok("accion", "lineas").stdout.splitlines()]

    def test_filas_agrupadas(self):
        self.m.sesion("suelta", self.m.home)
        self.m.sesion("mi-api", self.m.ruta("empresa/api"), marca="empresa/api")
        f = self.filas()
        self.assertEqual(f[0], "h:normal")
        self.assertIn("s:suelta", f)
        self.assertIn("s:_base", f)
        self.assertLess(f.index("g:empresa"), f.index("p:empresa/api"))
        self.assertNotIn("s:mi-api", f)  # la sesión aparece como su proyecto, no suelta
        self.assertIn("p:lab/nodo", f)

    def test_flotantes_ocultas(self):
        self.m.sesion("f-_base", self.m.home)
        self.assertNotIn("s:f-_base", self.filas())

    def test_abrir_crea_sesion_con_agentes(self):
        self.py("m.saltar = lambda s: None\nm.abrir(ws.cargar(), 'empresa', 'empresa/api')")
        ventanas = self.m.tmux("list-windows", "-t", "=em-api", "-F", "#{window_name}").split()
        self.assertEqual(ventanas[1:], ["claude", "opencode"])
        self.assertEqual(self.m.tmux("show", "-t", "=em-api:", "-qv", "@ws"), "empresa/api")
        texto = self.m.tmux("capture-pane", "-p", "-t", "=em-api:claude")
        self.assertIn("claude", texto)  # comando escrito, sin Enter

    def test_abrir_reutiliza_sesion_marcada(self):
        self.m.sesion("ContribApi", self.m.ruta("empresa/api"), marca="empresa/api")
        salida = self.py("print(m.sesion_de_proyecto(ws.cargar(), 'empresa/api'))")
        self.assertEqual(salida.strip(), "ContribApi")

    def test_vista_previa(self):
        prev = self.ws_ok("preview", "p:empresa/api").stdout
        for texto in ("empresa", "own", "kindling", "opencode"):
            self.assertIn(texto, prev)
        self.assertIn("the system's", self.ws_ok("preview", "p:aura/crm").stdout)

    def test_accion_propia_recibe_contexto(self):
        salida = self.m.home / "accion.txt"
        self.m.cfg["acciones"]["eco"] = {"tecla": "ctrl-o", "cmd": f'echo "$WS_GRUPO|$WS_PROYECTO|$WS_RUTA|$PWD" > {salida}'}
        self.m.escribir()
        self.ws_ok("accion", "propia", "p:empresa/api", "eco")
        g, p, ruta, pwd = salida.read_text().strip().split("|")
        self.assertEqual((g, p), ("empresa", "empresa/api"))
        self.assertEqual(os.path.realpath(ruta), os.path.realpath(pwd))

    def test_tema_desde_tmux(self):
        self.m.tmux("set", "-g", "@ws-color-accent", "#112233")
        self.m.tmux("set", "-g", "@ws-nerd-font", "on")
        salida = self.py("print(repr(m.ACENTO)); print(m.TEMA.iconos['organization'] != '')")
        self.assertIn("38;2;17;34;51", salida)
        self.assertIn("True", salida)

    def test_fzf_acepta_las_opciones(self):
        # Las opciones reales del selector con el fzf instalado (versión mínima incluida).
        salida = self.py("import subprocess\n"
                         "r = subprocess.run(m.FZF + ['--filter', 'api'], input='p:a\\tapi\\nx\\tzz',"
                         " capture_output=True, text=True, env=m.ENV_FZF)\n"
                         "print(r.returncode, r.stdout.strip(), r.stderr.strip())")
        self.assertTrue(salida.startswith("0 p:a"), salida)


if __name__ == "__main__":
    unittest.main()


class Idioma(CasoMundo):
    """Inglés por defecto; español por tmux, por ws.toml o por entorno."""

    def setUp(self):
        super().setUp()
        self.m.tmux_iniciar()

    def vista(self, **env):
        return self.ws_ok("preview", "p:empresa/api", **env).stdout

    def test_ingles_por_defecto(self):
        self.assertIn("open the session", self.vista())

    def test_espanol_por_opcion_de_tmux(self):
        self.m.tmux("set", "-g", "@ws-lang", "es")
        self.assertIn("abrir la sesión", self.vista())

    def test_espanol_por_ws_toml(self):
        self.m.escribir('\n[ui]\nlang = "es"\n')
        self.assertIn("abrir la sesión", self.vista())

    def test_entorno_manda_sobre_tmux(self):
        self.m.tmux("set", "-g", "@ws-lang", "es")
        self.assertIn("open the session", self.vista(WS_LANG="en"))

    def test_idioma_desconocido_cae_a_ingles(self):
        self.assertIn("open the session", self.vista(WS_LANG="xx"))

    def test_mismas_claves_en_todos_los_idiomas(self):
        import sys
        sys.path.insert(0, str(__import__("mundo").RAIZ / "src"))
        import i18n
        en = set(i18n.TEXTOS["en"])
        for codigo, textos in i18n.TEXTOS.items():
            self.assertEqual(set(textos) ^ en, set(), f"claves distintas en {codigo}")


class MotorEnAsistente(CasoMundo):
    def test_bloque_que_cambia_el_motor_pide_confirmacion(self):
        import sys
        pre = f"import sys; sys.path.insert(0, {str(RAIZ / 'src')!r}); import ws, ws_menu as m\n"
        codigo = (pre + "m.elegir = lambda *a, **k: (None, ['base', 'mm'])\n"
                  "preguntas = []\n"
                  "m.confirmar = lambda texto: preguntas.append(texto) or False\n"
                  "print(m.elegir_bloques(ws.cargar()), preguntas)")
        r = self.m.run([sys.executable, "-c", codigo])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("['base']", r.stdout)
        self.assertIn("minimax", r.stdout)

