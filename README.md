# Bâtiments 3D à la demande

Choisir des communes ou un rectangle sur une carte, et obtenir leurs bâtiments reconstruits
en 3D (toitures comprises) à partir du **LiDAR HD** et de la **BD TOPO** de l'IGN :

- une **carte 3D en ligne**, prête à partager ;
- une **couche pour QGIS** (GeoPackage, Lambert-93) ;
- un **modèle 3D** (OBJ) pour Blender, SketchUp…

Le calcul tourne gratuitement sur les machines de GitHub (GitHub Actions), avec la chaîne
[roofer de l'IGNfab](https://github.com/ignfab/roofer-with-ignf-datasets). Rien à installer
sur le poste des utilisateurs.

## Comment ça marche

1. La **page de sélection** (GitHub Pages) permet de choisir la zone et estime la durée.
2. « Lancer » ouvre un **formulaire GitHub pré-rempli** (une *issue*) : on clique sur *Create*.
3. **GitHub Actions** découpe la zone en carrés de 1 km², les répartit sur jusqu'à
   20 machines, reconstruit les bâtiments, assemble, convertit.
4. Les liens vers la carte 3D et le fichier zip sont ajoutés en commentaire dans l'issue.

Seuls le propriétaire et les collaborateurs du dépôt peuvent lancer un calcul.

## Mise en place (une seule fois)

1. **Créer un dépôt public** sur GitHub (ex. `batiments-3d-a-la-demande`) et y déposer tout le
   contenu de ce dossier, **y compris le dossier caché `.github`**.
2. **Autoriser les Actions à écrire** : *Settings > Actions > General > Workflow permissions*,
   cocher *Read and write permissions*, puis *Save*.
3. **Publier la page de sélection** : onglet *Actions*, workflow *Publier la page de sélection*,
   bouton *Run workflow*. Cela crée la branche `gh-pages`.
4. **Activer GitHub Pages** : *Settings > Pages*, *Source : Deploy from a branch*,
   branche `gh-pages`, dossier `/ (root)`, *Save*.
   La page est en ligne à l'adresse `https://<compte>.github.io/<dépôt>/`.
5. **Ajouter les collègues** : *Settings > Collaborators*, rôle *Write*.
   Chacun a besoin d'un compte GitHub gratuit.

Conseil : faites un premier essai sur un petit rectangle (quelques carrés).

## Réglages

| Fichier | Rôle |
|---|---|
| `config/reglages.sh` | Image Docker, version de la chaîne IGNfab, nombre de cartes gardées en ligne… |
| `config/roofer_params.txt` | Réglages supplémentaires de roofer (finesse des toits). Vide = réglages par défaut. |
| `site/index.html` | Page de sélection. |
| `site/visionneuse.html` | Gabarit de la carte 3D. Il peut être remplacé par une autre page, à condition qu'elle lise `3dtiles/tileset.json` (et, si besoin, `zone.json` : nom et emprise de la zone). |

## Limites

- Zone de **1 200 km² au maximum** par demande (au-delà, faire plusieurs demandes).
- **6 heures maximum** par machine (largement suffisant avec 20 machines).
- Seules les **4 dernières cartes** restent en ligne (réglable). Les fichiers zip restent
  téléchargeables dans *Releases* : supprimez de temps en temps les plus anciens.
- Reconstruction automatique : toitures complexes simplifiées, décalages possibles entre
  les dates du LiDAR et de la BD TOPO.

## Organisation du dépôt

```
.github/ISSUE_TEMPLATE/calcul-batiments-3d.yml   formulaire de demande
.github/workflows/calcul-batiments-3d.yml        le calcul (5 étapes)
.github/workflows/publier-site.yml                mise en ligne de la page de sélection
scripts/preparer.py      lit la demande, découpe en carrés, répartit en lots
scripts/calculer_lot.sh  reconstruit les carrés d'un lot (une machine)
scripts/assembler.py     fusionne sans doublons, filtre sur la zone, exports GeoJSON et OBJ
scripts/convertir.sh     3D Tiles (tyler), GeoPackage (ogr2ogr), zip
scripts/terminer.sh      téléchargement (Release), carte en ligne, message dans l'issue
scripts/publier.sh       mise à jour de la branche gh-pages
```

Données : IGN, Licence Ouverte. Logiciels : roofer et tyler (3DGI), chaîne IGNfab, CesiumJS, Leaflet.
