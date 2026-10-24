#!/usr/bin/env bash
# Étape 5 : dépôt du zip en téléchargement, publication de la carte, message dans la demande.
set -euo pipefail
SLUG=$(python3 -c "import json;print(json.load(open('sortie/stats.json'))['slug'])")
NOM=$(python3 -c "import json;print(json.load(open('sortie/stats.json'))['nom'])")
NB=$(python3 -c "import json;print(json.load(open('sortie/stats.json'))['batiments'])")
OWNER="${GITHUB_REPOSITORY_OWNER,,}"; REPO="${GITHUB_REPOSITORY#*/}"
CARTE="https://${OWNER}.github.io/${REPO}/cartes/${SLUG}/"
ZIP="https://github.com/${GITHUB_REPOSITORY}/releases/download/calcul-${NUM}/batiments_3d_${SLUG}.zip"

gh release delete "calcul-$NUM" -R "$GITHUB_REPOSITORY" --yes --cleanup-tag 2>/dev/null || true
gh release create "calcul-$NUM" "sortie/batiments_3d_${SLUG}.zip" -R "$GITHUB_REPOSITORY" \
  --title "Bâtiments 3D — $NOM" --notes-file sortie/notes.md

bash scripts/publier.sh "$SLUG"

{
  echo "✅ **Calcul terminé : $NB bâtiments reconstruits pour « $NOM »**"
  echo
  echo "- 🌐 **Carte 3D en ligne** : $CARTE"
  echo "  _(la mise en ligne peut prendre 1 à 2 minutes)_"
  echo "- ⬇️ **Fichiers** (GeoPackage pour QGIS, modèle 3D OBJ) : $ZIP"
  echo
  sed -n '/⚠️\|ℹ️/p' sortie/notes.md
} > sortie/message.md

gh issue comment "$NUM" -R "$GITHUB_REPOSITORY" --body-file sortie/message.md
gh issue close "$NUM" -R "$GITHUB_REPOSITORY"
