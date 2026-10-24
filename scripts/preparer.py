#!/usr/bin/env python3
"""
Étape 1 du calcul : lit la demande (corps de l'issue GitHub), récupère les contours
des communes ou le rectangle, découpe la zone en carrés de 1 km (Lambert-93) et répartit
les carrés en lots, un lot par machine de calcul.

Entrée  : variable d'environnement ISSUE_BODY (et ISSUE_NUMBER)
Sorties : dossier travail/ (tuiles.csv, zone_l93.json, zone.json, resume.json, annonce.md)
          + sorties GitHub (lots, nlots, slug)
"""
import json, math, os, re, sys, unicodedata, urllib.request

TAILLE = 1000        # côté des carrés, en mètres
MAX_TUILES = 1200    # garde-fou : ~ un grand EPCI
MAX_LOTS = 20        # machines en parallèle (limite gratuite de GitHub)
MAX_COMMUNES = 200
TRAVAIL = "travail"
os.makedirs(TRAVAIL, exist_ok=True)


def erreur(message):
    with open(f"{TRAVAIL}/erreur.md", "w") as f:
        f.write(f"**La demande n'a pas pu être traitée.**\n\n{message}\n\n"
                "Relancez une demande depuis la carte de sélection.")
    print("ERREUR :", message)
    sys.exit(1)


def lire(url):
    req = urllib.request.Request(url, headers={"User-Agent": "batiments-3d-a-la-demande"})
    for essai in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            dernier = e
    raise dernier


# --- Conversion GPS (WGS84) -> Lambert-93, sans dépendance externe ---
E = 0.0818191910428158; N = 0.7256077650532670; C = 11754255.426096
XS, YS, LON0 = 700000.0, 12655612.049876, math.radians(3)
def l93(lon, lat):
    p = math.radians(lat); s = math.sin(p)
    L = math.log(math.tan(math.pi/4 + p/2) * ((1 - E*s)/(1 + E*s))**(E/2))
    R = C * math.exp(-N * L); g = N * (math.radians(lon) - LON0)
    return XS + R*math.sin(g), YS - R*math.cos(g)


def slugifier(t):
    t = unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower()
    return "-".join("".join(c if c.isalnum() else " " for c in t).split())[:40] or "zone"


def dans(x, y, anneau):  # point dans un polygone (lancer de rayon)
    ok = False; j = len(anneau) - 1
    for i in range(len(anneau)):
        xi, yi = anneau[i]; xj, yj = anneau[j]
        if (yi > y) != (yj > y) and x < (xj-xi)*(y-yi)/(yj-yi) + xi:
            ok = not ok
        j = i
    return ok


# ---------- 1. Lire la demande ----------
corps = os.environ.get("ISSUE_BODY", "")
numero = os.environ.get("ISSUE_NUMBER", "0")
m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", corps, re.S) or re.search(r"(\{.*\})", corps, re.S)
if not m:
    erreur("La description de la zone est introuvable dans le formulaire.")
try:
    zone = json.loads(m.group(1))
except json.JSONDecodeError:
    erreur("La description de la zone est illisible (elle a peut-être été modifiée à la main).")

mn = re.search(r"###\s*Nom de la zone\s*\n+(.+)", corps)
nom = mn.group(1).strip() if mn else ""
if not nom or nom == "_No response_":
    nom = "Zone"
nom = nom[:80]

# ---------- 2. Contours de la zone (WGS84) ----------
anneaux_wgs = []
if zone.get("type") == "communes":
    codes = [str(c) for c in zone.get("codes", [])]
    if not codes:
        erreur("Aucune commune sélectionnée.")
    if len(codes) > MAX_COMMUNES:
        erreur(f"Trop de communes ({len(codes)}, maximum {MAX_COMMUNES}).")
    for code in codes:
        if not re.fullmatch(r"[0-9][0-9AB][0-9]{3}", code):
            erreur(f"Code commune invalide : {code}")
        try:
            c = lire(f"https://geo.api.gouv.fr/communes/{code}?fields=nom,code,contour")
        except Exception:
            erreur(f"Impossible de récupérer le contour de la commune {code} (geo.api.gouv.fr).")
        g = c.get("contour")
        if not g:
            erreur(f"Contour introuvable pour la commune {code}.")
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for p in polys:
            anneaux_wgs.append([tuple(pt[:2]) for pt in p[0]])
        print(f"  {c.get('nom', code)} ({code})")
elif zone.get("type") == "rectangle":
    try:
        w, s, e, n = [float(v) for v in zone["bbox"]]
    except Exception:
        erreur("Rectangle invalide.")
    if not (-6 < w < e < 10 and 41 < s < n < 52):
        erreur("Le rectangle doit se trouver en France métropolitaine.")
    anneaux_wgs.append([(w, s), (e, s), (e, n), (w, n)])
else:
    erreur("Type de zone inconnu (attendu : communes ou rectangle).")

lons = [p[0] for a in anneaux_wgs for p in a]; lats = [p[1] for a in anneaux_wgs for p in a]
emprise_wgs = {"west": min(lons), "south": min(lats), "east": max(lons), "north": max(lats)}

# ---------- 3. Découpage en carrés de 1 km ----------
anneaux = [[l93(*p) for p in a] for a in anneaux_wgs]
boites = [(min(p[0] for p in a), min(p[1] for p in a), max(p[0] for p in a), max(p[1] for p in a)) for a in anneaux]
x0 = math.floor(min(b[0] for b in boites) / TAILLE) * TAILLE
y0 = math.floor(min(b[1] for b in boites) / TAILLE) * TAILLE
x1 = max(b[2] for b in boites); y1 = max(b[3] for b in boites)

def touche(x, y):
    x2, y2 = x + TAILLE, y + TAILLE
    test = [(x + TAILLE/2, y + TAILLE/2), (x, y), (x2, y), (x, y2), (x2, y2)]
    for a, b in zip(anneaux, boites):
        if b[2] < x or b[0] > x2 or b[3] < y or b[1] > y2:
            continue
        if any(dans(px, py, a) for px, py in test):
            return True
        if any(x <= px <= x2 and y <= py <= y2 for px, py in a):
            return True
    return False

tuiles = []
x = x0
while x < x1:
    y = y0
    while y < y1:
        if touche(x, y):
            tuiles.append((x, y))
        y += TAILLE
    x += TAILLE

nt = len(tuiles)
if nt == 0:
    erreur("La zone ne couvre aucun carré de calcul.")
if nt > MAX_TUILES:
    erreur(f"La zone est trop grande : {nt} carrés de 1 km² (maximum {MAX_TUILES}). "
           "Découpez-la en plusieurs demandes.")

nlots = min(MAX_LOTS, nt)
with open(f"{TRAVAIL}/tuiles.csv", "w") as f:
    f.write("id;lot;xmin;ymin;xmax;ymax\n")
    for i, (x, y) in enumerate(tuiles, 1):
        f.write(f"{i};{(i - 1) % nlots};{x};{y};{x + TAILLE};{y + TAILLE}\n")

# ---------- 4. Fichiers pour les étapes suivantes ----------
slug = f"{numero}-{slugifier(nom)}"
json.dump(anneaux, open(f"{TRAVAIL}/zone_l93.json", "w"))
json.dump({"nom": nom, **emprise_wgs}, open(f"{TRAVAIL}/zone.json", "w"), ensure_ascii=False)
json.dump({"nom": nom, "slug": slug, "numero": numero, "ntuiles": nt, "nlots": nlots,
           "type": zone["type"]}, open(f"{TRAVAIL}/resume.json", "w"), ensure_ascii=False)

par_lot = math.ceil(nt / nlots)
duree = math.ceil(par_lot / 2) * 4 + 20   # ordre de grandeur, en minutes
with open(f"{TRAVAIL}/annonce.md", "w") as f:
    f.write(f"⏳ **Calcul lancé pour « {nom} »**\n\n"
            f"- {nt} carrés de 1 km², répartis sur {nlots} machine(s)\n"
            f"- Durée estimée : environ {duree} à {round(duree * 1.6)} minutes\n\n"
            "Le lien vers la carte 3D et les fichiers à télécharger sera ajouté ici à la fin du calcul.")

sortie = os.environ.get("GITHUB_OUTPUT")
if sortie:
    with open(sortie, "a") as f:
        f.write(f"lots={json.dumps(list(range(nlots)))}\n")
        f.write(f"nlots={nlots}\n")
        f.write(f"slug={slug}\n")
print(f"{nt} carrés, {nlots} lots, dossier « {slug} »")
