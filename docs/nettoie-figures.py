#!/usr/bin/env python3
"""Retire les figures des documents .md : elles ne doivent vivre
que dans les pages d'entree. Idempotent."""
import pathlib, sys

DOCS = ["01-cluster-proxmox.md", "02-vm-test-ha.md", "03-test-recette-HA.md",
        "04-journal-commandes.md", "pbs-01-sauvegarde.md", "pbs-02-journal-commandes.md",
        "cdc-santelia.md"]

def nettoie(path):
    p = pathlib.Path(path)
    if not p.exists():
        print("  absent    " + path); return 0
    blocs = p.read_text(encoding="utf-8").split("\n\n")
    gardes = [b for b in blocs if not (b.lstrip().startswith("![") and "figures/" in b)]
    n = len(blocs) - len(gardes)
    if n:
        p.write_text("\n\n".join(gardes), encoding="utf-8")
        print("  RETIRE " + str(n) + "  " + path)
    else:
        print("  rien      " + path)
    return n

if __name__ == "__main__":
    if not pathlib.Path("index.html").exists():
        print("Lance ce script depuis le dossier docs/ du depot."); sys.exit(1)
    total = 0
    for d in DOCS:
        total += nettoie(d)
    print()
    print("Figures retirees des documents : " + str(total))
