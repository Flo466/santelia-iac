#!/usr/bin/env bash
# build.sh -- regenere les .html de docs/ a partir des .md
# Convention : chaque .md commence par une ligne  "# Titre"
# Le CSS est dans style.css, partage par l'index et toutes les pages generees.
# Usage : ./build.sh   (lancable depuis n'importe ou)
set -euo pipefail

cd "$(dirname "$0")"
shopt -s nullglob

TODAY="$(date '+%d/%m/%Y')"
n=0

for md in *.md; do
  base="${md%.md}"

  # on ne genere pas de page pour les fichiers de service
  case "$base" in
    index|README|readme) continue ;;
  esac

  # titre = premiere ligne de type "# ..."
  title="$(sed -n '1{/^# /{s/^# *//;p;q}}' "$md" || true)"

  if [ -z "${title:-}" ]; then
    echo "  ATTENTION  $md : pas de titre H1 en premiere ligne, ignore"
    continue
  fi

  # la ligne H1 est retiree du corps : le bandeau l'affiche deja
  awk 'NR==1 && /^# / {next} {print}' "$md" > /tmp/_build_body.md

  echo "  OK  $base.html"
  pandoc /tmp/_build_body.md \
    -o "$base.html" \
    -s \
    --no-highlight \
    --template=tpl-doc.html \
    --metadata title="$title" \
    --metadata date="$TODAY"

  n=$((n+1))
done

rm -f /tmp/_build_body.md
echo "  -> $n document(s) regenere(s)"
