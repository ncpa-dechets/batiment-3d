#!/usr/bin/env bash
# Étape 2 du calcul, exécutée sur chaque machine : reconstruit les carrés d'un lot.
# Usage : bash scripts/calculer_lot.sh <numéro_du_lot>
# Résultat : resultats/tuile_<id>.city.jsonl pour chaque carré réussi,
#            resultats/etat_lot_<n>.txt (bilan : ok, vide, sans LiDAR, échec)
set -uo pipefail
LOT="$1"
RACINE="$(pwd)"
source config/reglages.sh
export RUNNER_IMAGE="$IMAGE"     # run.sh utilisera exactement cette image

mkdir -p resultats travail_tuiles
ETAT="$RACINE/resultats/etat_lot_${LOT}.txt"
: > "$ETAT"

# 1. Récupérer la chaîne de calcul IGNfab, à une version figée
git clone -q "$IGNFAB_DEPOT" ignfab
git -C ignfab checkout -q "$IGNFAB_VERSION"
# permettre de passer des réglages supplémentaires à roofer (config/roofer_params.txt)
sed -i 's|    -j "$ROOFER_JOBS" \\|    -j "$ROOFER_JOBS" $(cat /workspace/roofer_params.txt 2>/dev/null) \\|' \
  ignfab/scripts/run_workflow.sh
grep -v '^\s*#' config/roofer_params.txt 2>/dev/null | tr '\n' ' ' > ignfab/roofer_params.txt || true
echo "Réglages roofer supplémentaires : $(cat ignfab/roofer_params.txt)"

docker pull -q "$IMAGE"

# 2. Traiter un carré (2 essais en cas d'erreur réseau)
traiter() {
  IFS=';' read -r id lot xmin ymin xmax ymax <<< "$1"
  local d="$RACINE/travail_tuiles/tuile_$id" journal="$RACINE/travail_tuiles/tuile_$id.log"
  for essai in 1 2; do
    rm -rf "$d"
    if (cd "$RACINE/ignfab" && ./run.sh --bbox "$xmin" "$ymin" "$xmax" "$ymax" --out "$d" \
          --jobs 2 > "$journal" 2>&1 < /dev/null); then
      f=$(ls "$d"/run-*/roofer_output/*.city.jsonl 2>/dev/null | head -1)
      if [ -n "$f" ]; then
        cp "$f" "$RACINE/resultats/tuile_$id.city.jsonl"
        rm -rf "$d"
        echo "$id;ok" >> "$ETAT"; echo "carré $id : terminé"
        return 0
      fi
    fi
    if grep -q "building query returned no features" "$journal"; then
      rm -rf "$d"; echo "$id;vide" >> "$ETAT"; echo "carré $id : aucun bâtiment"; return 0
    fi
    if grep -q "LiDAR tile query returned no feature" "$journal"; then
      rm -rf "$d"; echo "$id;sans_lidar" >> "$ETAT"; echo "carré $id : pas de LiDAR HD disponible"; return 0
    fi
    echo "carré $id : erreur (essai $essai)"; tail -n 5 "$journal"
    sleep 20
  done
  rm -rf "$d"; echo "$id;echec" >> "$ETAT"
  return 0
}
export -f traiter
export RACINE ETAT

# 3. Carrés de ce lot, traités par paquets de $PARALLELE
tail -n +2 travail/tuiles.csv | tr -d '\r' | awk -F';' -v l="$LOT" '$2==l' \
  | xargs -d '\n' -P "$PARALLELE" -I{} bash -c 'traiter "$1"' _ {}

echo "Bilan du lot $LOT :"; cut -d';' -f2 "$ETAT" | sort | uniq -c
