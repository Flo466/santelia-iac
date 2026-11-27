#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corrige-doc.py — cinq corrections de coherence sur la documentation Santelia.

Usage :
    python3 corrige-doc.py --dry-run     # simulation
    python3 corrige-doc.py               # applique

Idempotent : relancable sans risque.
"""
import sys
import pathlib

SIMULE = "--dry-run" in sys.argv


def patch(chemin, remplacements, nom):
    p = pathlib.Path(chemin)
    if not p.exists():
        print(f"  [ABSENT] {chemin}")
        return 0
    t = p.read_text(encoding="utf-8")
    originel = t
    faits = []
    for vieux, neuf, libelle in remplacements:
        if neuf in t and vieux not in t:
            faits.append(f"deja fait : {libelle}")
        elif vieux in t:
            t = t.replace(vieux, neuf, 1)
            faits.append(f"OK : {libelle}")
        else:
            faits.append(f"NON TROUVE : {libelle}")
    if t != originel and not SIMULE:
        p.write_text(t, encoding="utf-8")
    for f in faits:
        print(f"  {f}")
    return 1 if t != originel else 0


print("=== 1. pbs-01 : le chiffre a ne pas annoncer ===")
patch("pbs-01-sauvegarde.md", [(
    '« 30 minutes » décrit la fréquence de la copie. Annoncé comme perte maximale, il est faux d\'un facteur 25',
    '« 30 minutes » décrit le délai de propagation vers la copie, pas une perte maximale. Annoncé comme tel, il est faux d\'un facteur 25',
    'délai de propagation au lieu de fréquence'
)], "pbs-01")

print()
print("=== 2. pbs-02 : le seuil d'extension du pool ===")
patch("pbs-02-journal-commandes.md", [(
    "Aucune valeur n'est définie dans la configuration courante, les valeurs par défaut sont donc\ninactives : le seuil effectif est de 100 %, l'extension automatique ne se déclenche jamais.",
    "Au moment du relevé initial, aucune valeur n'était définie dans la configuration courante : le\nseuil effectif était de 100 %, l'extension automatique ne se déclenchait jamais.\n\n**État actuel de l'hôte :** seuil fixé à **80 %**, extension de **10 %**. Le contrôle se fait par\n`lvmconfig --type current`.",
    "relevé initial, état actuel précisé"
)], "pbs-02")

print()
print("=== 3. audit : séparateur manquant après 1.3 ===")
patch("audit-santelia.md", [(
    "et non sur une maquette reconstituée pour l'exercice.\n\n## 2. Méthode et outillage",
    "et non sur une maquette reconstituée pour l'exercice.\n\n---\n\n## 2. Méthode et outillage",
    "séparateur ajouté"
)], "audit")

print()
print("=== 4. audit : numérotation de la section 2 ===")
patch("audit-santelia.md", [
    ("### 2.3 Vocabulaire de l'analyse", "### 2.4 Vocabulaire de l'analyse", "2.3 devient 2.4"),
    ("### 2.2 Dimensionnement", "### 2.3 Dimensionnement", "2.2 devient 2.3"),
    ("### 2.1 bis Construction de la station", "### 2.2 Construction de la station", "2.1 bis devient 2.2"),
], "audit")

print()
print("=== 5. audit : phrase de conséquence perdue en 3.5 ===")
patch("audit-santelia.md", [(
    "**Aucun service NFS.** Le port 2049 est fermé sur les trois nœuds, contrairement à la configuration de référence. Le stockage des machines virtuelles n'est pas exposé par ce protocole.",
    "**Aucun service NFS.** Le port 2049 est fermé sur les trois nœuds, contrairement à la configuration de référence. Le stockage des machines virtuelles n'est pas exposé par ce protocole.\n\n**Conséquence sur l'analyse.** Le constat le plus critique de la référence — un partage de stockage lisible par toute machine du réseau — n'existe pas dans ce périmètre. Les constats retenus portent donc sur les services effectivement exposés.",
    "conséquence réintroduite"
)], "audit")

print()
print("=== Termine ===")
if SIMULE:
    print("Simulation : aucun fichier ecrit. Relance sans --dry-run.")
else:
    print("Fichiers ecrits. Pense a ./build.sh puis git diff.")
