#!/usr/bin/env python3
"""Ejecuta las pruebas de ws en paralelo: un proceso por módulo, cada uno con
sus propios mundos aislados (HOME, cuentas y servidor de tmux falsos).

  python3 tests/run.py            todas
  python3 tests/run.py --rapido   sin las de punta a punta (pty + popups)
  python3 tests/run.py git tmux   solo esos módulos (test_git, test_tmux)
"""
import concurrent.futures as cf
import os
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    modulos = sorted(p.stem for p in AQUI.glob("test_*.py"))
    if args:
        modulos = [m for m in modulos if m.removeprefix("test_") in args]
    if "--rapido" in sys.argv:
        modulos = [m for m in modulos if m != "test_e2e"]
    inicio = time.time()

    def correr(mod):
        t = time.time()
        r = subprocess.run([sys.executable, "-m", "unittest", mod], cwd=AQUI,
                           capture_output=True, text=True)
        return mod, r.returncode, r.stderr, time.time() - t

    fallos = 0
    with cf.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
        for mod, rc, salida, dur in ex.map(correr, modulos):
            lineas = [l for l in salida.splitlines() if l.startswith("Ran ")]
            resumen = lineas[-1].removeprefix("Ran ") if lineas else "?"
            marca = "\033[32m✓\033[0m" if rc == 0 else "\033[31m✗\033[0m"
            print(f"{marca} {mod:<16} {resumen:<18} {dur:5.1f}s")
            for l in salida.splitlines():
                if l.strip().startswith(("gh directo",)):
                    print(f"    {l.strip()}")
            if rc:
                fallos += 1
                print(salida)
    print(f"\n{len(modulos) - fallos}/{len(modulos)} módulos bien en {time.time() - inicio:.1f}s")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
