#!/usr/bin/env bash
# Étape 4 : conversions avec les outils de l'image Docker
#  - tyler   : sortie/source -> sortie/carte/3dtiles (carte 3D web)
#  - ogr2ogr : sortie/batiments_3d.geojson -> sortie/batiments_3d.gpkg (QGIS)
# puis création du zip à télécharger.
set -euo pipefail
source config/reglages.sh
SLUG=$(python3 -c "import json;print(json.load(open('sortie/stats.json'))['slug'])")
ZMIN=$(python3 -c "import json,math;print(math.floor(json.load(open('sortie/stats.json'))['zmin'])-20)")
ZMAX=$(python3 -c "import json,math;print(math.ceil(json.load(open('sortie/stats.json'))['zmax'])+20)")
U="$(id -u):$(id -g)"

docker pull -q "$IMAGE"

echo "Conversion en 3D Tiles (altitudes de $ZMIN à $ZMAX m)"
docker run --rm --user "$U" -v "$PWD/sortie":/data \
  --entrypoint /opt/3dbag-pipeline/tools/bin/tyler "$IMAGE" \
  --output=/data/carte/3dtiles \
  --3dtiles-metadata-class=building \
  --object-type=BuildingPart --lod-building-part=2.2 \
  --include-parent-attributes \
  --grid-minz="$ZMIN" --grid-maxz="$ZMAX" \
  /data/source
test -f sortie/carte/3dtiles/tileset.json

echo "Conversion en GeoPackage"
docker run --rm --user "$U" -v "$PWD/sortie":/data --entrypoint bash "$IMAGE" -lc \
  'export PATH=/opt/3dbag-pipeline/tools/bin:$PATH;
   ogr2ogr -f GPKG /data/batiments_3d.gpkg /data/batiments_3d.geojson \
     -a_srs EPSG:2154 -nln batiments_3d -nlt MULTIPOLYGONZ'
test -f sortie/batiments_3d.gpkg

echo "Création du fichier à télécharger"
(cd sortie && zip -q -9 "batiments_3d_${SLUG}.zip" batiments_3d.gpkg batiments_3d.obj LISEZMOI.txt)
ls -lh sortie/*.zip
du -sh sortie/carte
