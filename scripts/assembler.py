#!/usr/bin/env python3
"""
Étape 3 du calcul : assemble les carrés reconstruits par toutes les machines.
- écarte les doublons (bâtiment calculé dans deux carrés voisins) grâce à l'identifiant BD TOPO
- ne garde que les bâtiments dont le centre est dans la zone demandée
- écrit : sortie/source/batiments.city.jsonl (pour tyler, carte 3D)
          sortie/batiments_3d.geojson (converti ensuite en GeoPackage pour QGIS)
          sortie/batiments_3d.obj (modèle 3D pour Blender, SketchUp…)
          sortie/stats.json, sortie/LISEZMOI.txt, sortie/notes.md, sortie/carte/ (page + zone.json)
"""
import glob, json, os, shutil

os.makedirs("sortie/source", exist_ok=True)
os.makedirs("sortie/carte", exist_ok=True)
resume = json.load(open("travail/resume.json"))
anneaux = json.load(open("travail/zone_l93.json"))
boites = [(min(p[0] for p in a), min(p[1] for p in a), max(p[0] for p in a), max(p[1] for p in a)) for a in anneaux]
# origine du modèle OBJ : coin sud-ouest de la zone (évite les très grands nombres)
OX = round(min(b[0] for b in boites)); OY = round(min(b[1] for b in boites))


def dans(x, y, anneau):
    ok = False; j = len(anneau) - 1
    for i in range(len(anneau)):
        xi, yi = anneau[i]; xj, yj = anneau[j]
        if (yi > y) != (yj > y) and x < (xj-xi)*(y-yi)/(yj-yi) + xi:
            ok = not ok
        j = i
    return ok


def dans_zone(x, y):
    return any(b[0] <= x <= b[2] and b[1] <= y <= b[3] and dans(x, y, a) for a, b in zip(anneaux, boites))


def surfaces(geom):
    t, b = geom.get("type"), geom.get("boundaries", [])
    if t == "Solid":
        return [s for coque in b for s in coque]
    if t in ("MultiSolid", "CompositeSolid"):
        return [s for solide in b for coque in solide for s in coque]
    if t in ("MultiSurface", "CompositeSurface"):
        return b
    return []


def meilleure(geoms):
    """La géométrie la plus détaillée : LoD 2.2 si présente."""
    if not geoms:
        return None
    for g in geoms:
        if str(g.get("lod")) == "2.2":
            return g
    return sorted(geoms, key=lambda g: str(g.get("lod")))[-1]


def simples(attrs):
    return {k: v for k, v in (attrs or {}).items() if isinstance(v, (str, int, float, bool))}


fichiers = sorted(glob.glob("resultats/**/*.city.jsonl", recursive=True))
print(f"{len(fichiers)} carrés reconstruits à assembler")

vus = set(); n_doublons = n_hors_zone = n_garde = 0
zmin, zmax = 1e9, -1e9
entete = None; S = T = None
nv_obj = 0  # nombre de sommets déjà écrits dans l'OBJ

seq = open("sortie/source/batiments.city.jsonl", "w")
gj = open("sortie/batiments_3d.geojson", "w")
gj.write('{"type":"FeatureCollection","name":"batiments_3d",'
         '"crs":{"type":"name","properties":{"name":"urn:ogc:def:crs:EPSG::2154"}},"features":[\n')
obj = open("sortie/batiments_3d.obj", "w")
obj.write(f"# Bâtiments 3D — {resume['nom']}\n"
          f"# Coordonnées en mètres, Lambert-93 décalé : X = x - {OX}, Y = altitude NGF, Z = -(y - {OY})\n")
premier_gj = True

for f in fichiers:
    with open(f) as src:
        lignes = src.read().splitlines()
    if not lignes:
        continue
    tete = json.loads(lignes[0])
    s, t = tete["transform"]["scale"], tete["transform"]["translate"]
    if entete is None:
        entete = tete; S, T = s, t
        seq.write(json.dumps(entete, separators=(",", ":")) + "\n")
    for ligne in lignes[1:]:
        if not ligne.strip():
            continue
        feat = json.loads(ligne)
        ident = feat.get("id")
        if ident in vus:
            n_doublons += 1
            continue
        # coordonnées réelles (Lambert-93, altitude NGF)
        reels = [[v[k] * s[k] + t[k] for k in range(3)] for v in feat["vertices"]]
        if not reels:
            continue
        cx = sum(p[0] for p in reels) / len(reels); cy = sum(p[1] for p in reels) / len(reels)
        if not dans_zone(cx, cy):
            n_hors_zone += 1
            continue
        vus.add(ident); n_garde += 1
        # 1) CityJSONSeq commun (recalage sur le repère de la première tuile)
        if s != S or t != T:
            feat["vertices"] = [[round((p[k] - T[k]) / S[k]) for k in range(3)] for p in reels]
        seq.write(json.dumps(feat, separators=(",", ":")) + "\n")

        # 2) surfaces 3D du bâtiment (toutes ses parties, au niveau de détail le plus fin)
        objets = feat["CityObjects"]
        attrs = simples(objets.get(ident, {}).get("attributes"))
        attrs["identifiant"] = ident
        polys = []
        for o in objets.values():
            g = meilleure(o.get("geometry"))
            if g:
                polys += surfaces(g)
        if not polys:
            continue
        geo = []
        utilises = {}
        faces = []
        for surf in polys:
            anneaux_surf = []
            for k, anneau in enumerate(surf):
                if len(anneau) < 3:
                    continue
                pts = [reels[i] for i in anneau]
                for p in pts:
                    zmin = min(zmin, p[2]); zmax = max(zmax, p[2])
                anneaux_surf.append([[round(c, 3) for c in p] for p in pts + [pts[0]]])
                if k == 0:  # l'OBJ ne gère pas les trous : contour extérieur seulement
                    faces.append([utilises.setdefault(i, len(utilises)) for i in anneau])
            if anneaux_surf:
                geo.append(anneaux_surf)
        gj.write(("" if premier_gj else ",\n") + json.dumps(
            {"type": "Feature", "properties": attrs,
             "geometry": {"type": "MultiPolygon", "coordinates": geo}}, separators=(",", ":")))
        premier_gj = False

        # 3) OBJ (axe vertical = Y, convention des logiciels 3D)
        obj.write(f"o {ident}\n")
        for i, _ in sorted(utilises.items(), key=lambda kv: kv[1]):
            x, y, z = reels[i]
            obj.write(f"v {x - OX:.3f} {z:.3f} {-(y - OY):.3f}\n")
        for face in faces:
            obj.write("f " + " ".join(str(nv_obj + j + 1) for j in face) + "\n")
        nv_obj += len(utilises)

gj.write("\n]}\n")
seq.close(); gj.close(); obj.close()

# ---------- bilan des carrés ----------
etats = {}
for f in glob.glob("resultats/**/etat_lot_*.txt", recursive=True):
    for l in open(f):
        if ";" in l:
            etats[l.split(";")[0]] = l.strip().split(";")[1]
compte = {k: list(etats.values()).count(k) for k in ("ok", "vide", "sans_lidar", "echec")}
manquants = resume["ntuiles"] - len(etats)   # carrés dont la machine n'a rien renvoyé

stats = {"nom": resume["nom"], "slug": resume["slug"], "batiments": n_garde, "doublons": n_doublons,
         "hors_zone": n_hors_zone, "ntuiles": resume["ntuiles"], "carres": compte,
         "carres_sans_reponse": manquants,
         "zmin": round(zmin, 1) if n_garde else 0, "zmax": round(zmax, 1) if n_garde else 0}
json.dump(stats, open("sortie/stats.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(stats, ensure_ascii=False, indent=1))
if n_garde == 0:
    raise SystemExit("Aucun bâtiment reconstruit dans la zone.")

# ---------- textes ----------
alerte = ""
if compte["echec"] or manquants:
    alerte = (f"\n⚠️ {compte['echec'] + manquants} carré(s) de 1 km² n'ont pas pu être calculés : "
              "des bâtiments peuvent manquer dans ces secteurs.\n")
if compte["sans_lidar"]:
    alerte += (f"\nℹ️ {compte['sans_lidar']} carré(s) ne sont pas encore couverts par le LiDAR HD de l'IGN.\n")

open("sortie/LISEZMOI.txt", "w").write(f"""Bâtiments 3D — {resume['nom']}
{'=' * (16 + len(resume['nom']))}

{n_garde} bâtiments reconstruits à partir du LiDAR HD et de la BD TOPO (IGN),
avec le logiciel roofer (3DGI) et la chaîne de l'IGNfab. Données sous Licence Ouverte (IGN).
{alerte}
batiments_3d.gpkg   Couche pour QGIS, en Lambert-93 (EPSG:2154), altitudes NGF.
                    Un objet par bâtiment (toutes ses faces), avec l'identifiant BD TOPO.
                    Dans QGIS : Vue > Nouvelle vue cartographique 3D.

batiments_3d.obj    Modèle 3D pour Blender, SketchUp, Rhino… (un objet par bâtiment).
                    Unités en mètres. Axe vertical = Y.
                    Origine décalée : X = x Lambert-93 - {OX} ; Z = -(y Lambert-93 - {OY}) ;
                    Y = altitude NGF.

Reconstruction automatique : les toitures complexes sont simplifiées, et un bâtiment
récent ou démoli peut être erroné si le relevé LiDAR et la BD TOPO n'ont pas la même date.
""")

open("sortie/notes.md", "w").write(
    f"**{n_garde} bâtiments** reconstruits pour « {resume['nom']} ».\n\n"
    "Le fichier zip contient une couche pour QGIS (GeoPackage) et un modèle 3D (OBJ), "
    "avec un fichier LISEZMOI.\n" + alerte)

shutil.copy("site/visionneuse.html", "sortie/carte/index.html")
shutil.copy("travail/zone.json", "sortie/carte/zone.json")
