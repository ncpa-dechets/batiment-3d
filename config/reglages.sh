# Réglages communs aux scripts de calcul (modifiables)

# Image Docker contenant roofer, tyler, PDAL et GDAL (la même que sur votre PC)
IMAGE="3dgi/3dbag-pipeline-tools:2026.07.29"

# Version figée de la chaîne IGNfab, pour qu'une mise à jour de leur dépôt ne casse rien
IGNFAB_DEPOT="https://github.com/ignfab/roofer-with-ignf-datasets.git"
IGNFAB_VERSION="ed5641853f73593ab99ecb5d4ae223ff6f615e53"

# Nombre de carrés traités en même temps sur chaque machine (4 processeurs)
PARALLELE=2

# Nombre de cartes 3D conservées en ligne (les plus anciennes sont retirées du site,
# leurs fichiers restent téléchargeables dans les « Releases »)
CARTES_A_GARDER=4
