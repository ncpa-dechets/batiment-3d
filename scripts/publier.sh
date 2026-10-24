#!/usr/bin/env bash
# Met à jour le site GitHub Pages (branche gh-pages) :
#  - copie la page de sélection (site/index.html)
#  - ajoute, si un dossier est donné, la nouvelle carte 3D dans cartes/<dossier>/
#  - ne garde que les $CARTES_A_GARDER cartes les plus récentes
# La branche est réécrite en un seul commit pour que le dépôt ne grossisse pas indéfiniment.
# Usage : bash scripts/publier.sh [dossier]
set -euo pipefail
source config/reglages.sh
DOSSIER="${1:-}"
URL="${PAGES_URL:-https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git}"

for essai in 1 2 3 4 5; do
  rm -rf pages
  ATTENDU=""
  if git clone -q --depth 1 --branch gh-pages "$URL" pages 2>/dev/null; then
    ATTENDU=$(git -C pages rev-parse HEAD)
    rm -rf pages/.git
  else
    mkdir -p pages
  fi
  cp site/index.html pages/index.html
  touch pages/.nojekyll
  mkdir -p pages/cartes
  [ -f pages/cartes/liste.json ] || echo "[]" > pages/cartes/liste.json

  if [ -n "$DOSSIER" ]; then
    rm -rf "pages/cartes/$DOSSIER"
    cp -r sortie/carte "pages/cartes/$DOSSIER"
    DOSSIER="$DOSSIER" GARDER="$CARTES_A_GARDER" python3 - << 'PY'
import json, os, shutil, datetime
liste = json.load(open("pages/cartes/liste.json"))
stats = json.load(open("sortie/stats.json"))
d = os.environ["DOSSIER"]
repo = os.environ["GITHUB_REPOSITORY"]; num = os.environ.get("NUM", "")
liste = [c for c in liste if c.get("dossier") != d]
liste.insert(0, {"dossier": d, "nom": stats["nom"], "batiments": stats["batiments"],
                 "date": datetime.date.today().isoformat(),
                 "telechargement": f"https://github.com/{repo}/releases/download/calcul-{num}/batiments_3d_{d}.zip",
                 "demande": f"https://github.com/{repo}/issues/{num}"})
garder = int(os.environ["GARDER"])
for c in liste[garder:]:
    shutil.rmtree(f"pages/cartes/{c['dossier']}", ignore_errors=True)
json.dump(liste[:garder], open("pages/cartes/liste.json", "w"), ensure_ascii=False, indent=1)
PY
  fi

  (
    cd pages
    git init -q -b gh-pages
    git config user.name "github-actions[bot]"
    git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
    git add -A
    git commit -q -m "Publication du $(date -u +%F\ %H:%M)"
    # n'écrase la branche que si personne ne l'a modifiée entre-temps
    git push -q --force-with-lease="gh-pages:${ATTENDU}" "$URL" gh-pages
  ) && { echo "Site publié."; exit 0; }
  echo "Publication concurrente détectée, nouvel essai dans 30 s…"; sleep 30
done
echo "Échec de la publication du site."; exit 1
