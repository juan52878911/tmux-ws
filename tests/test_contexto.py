"""Resolución de contexto y herencia de bloques."""
import json
import os
import unittest

from escenario import CasoMundo


class Contexto(CasoMundo):
    def ctx(self, cwd, **env):
        r = self.ws_ok("contexto", "--json", cwd=cwd, **env)
        return json.loads(r.stdout) if r.stdout.strip() != "{}" else {}

    def test_fuera_de_todo_es_normal(self):
        self.assertEqual(self.ws_ok("contexto", cwd=self.m.home).stdout.strip(), "normal")

    def test_carpeta_de_proyecto_y_subcarpetas(self):
        api = self.m.ruta("empresa/api")
        (api / "src/deep").mkdir(parents=True)
        for cwd in (api, api / "src/deep"):
            c = self.ctx(cwd)
            self.assertEqual((c["grupo"], c["proyecto"], c["origen"]), ("empresa", "empresa/api", "carpeta"))

    def test_proyecto_anidado_gana_al_contenedor(self):
        self.assertEqual(self.ctx(self.m.ruta("aura/web"))["proyecto"], "aura/web")
        self.assertEqual(self.ctx(self.m.ruta("aura/crm"))["proyecto"], "aura/crm")

    def test_raiz_de_organizacion_sin_proyecto(self):
        raiz = self.m.home / "Orgs/empresa/suelto"
        raiz.mkdir(parents=True)
        c = self.ctx(raiz)
        self.assertEqual((c["grupo"], c["proyecto"]), ("empresa", None))

    def test_enlace_simbolico_resuelve_igual(self):
        enlace = self.m.home / "atajo-api"
        enlace.symlink_to(self.m.ruta("empresa/api"))
        self.assertEqual(self.ctx(enlace)["proyecto"], "empresa/api")

    def test_prefijo_de_nombre_no_confunde(self):
        # ~/src/empresa-api-v2 no está dentro de ~/src/empresa-api
        gemela = self.m.home / "src/empresa-api-v2"
        gemela.mkdir()
        self.assertEqual(self.ws_ok("contexto", cwd=gemela).stdout.strip(), "normal")


class Herencia(CasoMundo):
    def efectiva(self, cwd):
        return json.loads(self.ws_ok("contexto", "--json", cwd=cwd).stdout)["efectiva"]

    def test_union_de_bloques_de_org_y_proyecto(self):
        ef = self.efectiva(self.m.ruta("lab/nodo"))
        self.assertEqual(ef["bloques"], ["base", "obsidian", "nodo", "mm"])
        self.assertEqual(ef["mcps"], ["kindling", "tree-sitter", "obsidian"])
        self.assertEqual(ef["herramientas"], ["nodejs_24"])
        self.assertEqual(ef["claude_motor"], "minimax")

    def test_quitar_elimina_lo_heredado(self):
        self.assertNotIn("tree-sitter", self.efectiva(self.m.ruta("aura/web"))["mcps"])

    def test_variables_bloque_org_proyecto(self):
        api = self.efectiva(self.m.ruta("empresa/api"))["env"]
        self.assertEqual(api["AWS_PROFILE"], "desde-proyecto")
        raiz = self.m.home / "Orgs/empresa"
        raiz.mkdir(parents=True, exist_ok=True)
        self.assertEqual(self.efectiva(raiz)["env"]["AWS_PROFILE"], "desde-org")


if __name__ == "__main__":
    unittest.main()
