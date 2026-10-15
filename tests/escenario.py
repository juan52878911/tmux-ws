"""Escenario estándar: varias organizaciones con identidades distintas.

  empresa   cuenta GitHub propia (conectada), Claude propio, github_orgs empresa-co,
            variables propias (una con secreto), bloques base + opencode
  aura      cuenta personal, Claude personal, correo propio
  nueva     cuenta GitHub propia SIN conectar
  lab       entorno con obsidian (MCP con secreto) y herramientas Nix

Proyectos: empresa/api (repo de empresa-co), empresa/propio (repo personal
dentro de la org: excepciones github/claude = personal), aura/crm y aura/web
anidado dentro de crm (gana el más profundo), nueva/x y lab/nodo.
"""
import unittest

from mundo import Mundo


def estandar():
    m = Mundo()
    (m.secreto("KLING_TOKEN", "k-secreto")
      .secreto("OBSIDIAN_API_KEY", "obs-secreto")
      .secreto("MINIMAX_API_KEY", "mm-secreto")
      .secreto("NPM_EMP", "npm-secreto"))
    (m.mcp("kindling", url="https://mcp.ejemplo.dev/_all", headers={"Authorization": "Bearer ${KLING_TOKEN}"})
      .mcp("tree-sitter", cmd=["npx", "-y", "mcp-server-tree-sitter"])
      .mcp("obsidian", cmd=["~/bin/obsidian-mcp"], env={"OBSIDIAN_API_KEY": "${OBSIDIAN_API_KEY}"}))
    (m.bloque("base", mcps=["kindling", "tree-sitter"], agentes=["claude"])
      .bloque("oc", agentes=["opencode"])
      .bloque("obsidian", mcps=["obsidian"])
      .bloque("nodo", herramientas=["nodejs_24"])
      .bloque("mm", claude_motor="minimax")
      .bloque("aws", env={"AWS_PROFILE": "desde-bloque"}))
    m.cfg["motores"]["minimax"] = {"url": "https://api.minimax.io/anthropic", "modelo": "MiniMax-M2.7",
                                   "token": "MINIMAX_API_KEY"}
    m.cfg["agentes"]["claude"] = {"cmd": "claude"}
    m.cuenta_github("empresa", usuario="yo-empresa", token="tok-empresa")
    m.cuenta_github("nueva", usuario="yo-nueva")  # sin token: no conectada
    m.organizacion("empresa", github="empresa", claude="propia", git_correo="yo@empresa.com",
                   github_orgs=["empresa-co"], bloques=["base", "oc", "aws"],
                   env={"NPM_TOKEN": "${NPM_EMP}", "AWS_PROFILE": "desde-org"},
                   path=["~/.npm-empresa/bin"])
    m.organizacion("aura", github="personal", claude="personal", git_correo="yo@aura.dev", bloques=["base"])
    m.organizacion("nueva", github="nueva", claude="personal", bloques=["base"])
    m.entorno("lab", bloques=["base", "obsidian"])
    m.proyecto("empresa/api", remoto="https://github.com/empresa-co/api.git",
               env={"AWS_PROFILE": "desde-proyecto"}, path=["~/api-bin", "~/.npm-empresa/bin"])
    m.proyecto("empresa/propio", remoto="https://github.com/yo-personal/propio.git",
               github="personal", claude="personal")
    m.proyecto("aura/crm")
    m.proyecto("aura/web", ruta=m.ruta("aura/crm") / "web", git=False, quitar=["tree-sitter"])
    m.proyecto("nueva/x")
    m.proyecto("lab/nodo", bloques=["nodo", "mm"])
    m.escribir()
    m.instalar_shims()
    return m


class CasoMundo(unittest.TestCase):
    """Cada prueba en su propio mundo; se borra al terminar."""

    def setUp(self):
        self.m = estandar()
        self.addCleanup(self.m.cerrar)

    def ws_ok(self, *args, **kw):
        r = self.m.ws(*args, **kw)
        self.assertEqual(r.returncode, 0, f"ws {' '.join(args)} falló:\n{r.stderr}")
        return r
