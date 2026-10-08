#!/usr/bin/env python3
import pathlib, sys

FIG01 = "![Vue macro de l'infrastructure — le cluster et le serveur de sauvegarde sur un premier châssis, la supervision et la copie secondaire sur un second.](figures/fig-01-architecture-macro.svg)"
FIG02 = "![Logique de la brique haute disponibilité — quorum à deux votes sur trois, réplication des volumes, et déroulé mesuré de la bascule.](figures/fig-02-bloc1-haute-disponibilite.svg)"
FIG03 = "![Stratégie 3-2-1 — les trois copies, leur support, et les mesures relevées sur la sauvegarde et la restauration.](figures/fig-03-bloc2-sauvegarde.svg)"

CIBLES = [
    ("01-cluster-proxmox.md", [
        ("virtuellement séparés.", FIG01),
        ("pour obtenir la même résilience.", FIG02),
    ]),
    ("pbs-01-sauvegarde.md", [
        ("## 2. Architecture retenue", FIG01),
        ("justifie la troisième copie sur une machine distincte.", FIG03),
    ]),
]

def insere(path, paires):
    p = pathlib.Path(path)
    if not p.exists():
        print("  ABSENT    " + path); return 0
    blocs = p.read_text(encoding="utf-8").split("\n\n")
    n = 0
    for ancre, fig in paires:
        ref = fig.split("](")[1]
        if any(ref in b for b in blocs):
            print("  deja la   " + path); continue
        for i, b in enumerate(blocs):
            if ancre in b:
                blocs.insert(i + 1, fig)
                print("  INSERE    " + path + "  -> " + ref)
                n += 1
                break
        else:
            print("  ANCRE KO  " + path + "  -> " + ancre[:50])
    p.write_text("\n\n".join(blocs), encoding="utf-8")
    return n

def gabarit():
    p = pathlib.Path("tpl-doc.html")
    if not p.exists():
        print("  ABSENT    tpl-doc.html"); return
    s = p.read_text(encoding="utf-8")
    avant = '<p class="eyebrow">Sant&eacute;lia &middot; Proxmox VE &middot; haute disponibilit&eacute;</p>'
    apres = '<p class="eyebrow">Sant&eacute;lia &middot; dossier technique</p>'
    if avant in s:
        p.write_text(s.replace(avant, apres), encoding="utf-8")
        print("  CORRIGE   tpl-doc.html")
    elif apres in s:
        print("  deja fait tpl-doc.html")
    else:
        print("  ATTENTION tpl-doc.html : ligne non reconnue")

if __name__ == "__main__":
    if not pathlib.Path("01-cluster-proxmox.md").exists():
        print("Lance ce script depuis le dossier docs/ du depot."); sys.exit(1)
    total = 0
    for c, pa in CIBLES:
        total += insere(c, pa)
    gabarit()
    print()
    print("Figures ajoutees :", total)
    print("Etape suivante   : ./build.sh")
