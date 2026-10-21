# Génère la page d'accueil de gh-pages : un tableau listant toutes les branches de l'IG déjà
# publiées en ci-build (une preview par branche, à l'URL ./<branche>/ig/), avec la date de
# dernière mise à jour de chacune, la branche par défaut du repo mise en avant, et un bandeau
# d'avertissement pointant vers l'URL canonique si l'IG a déjà une version officiellement publiée.
#
# Appelé depuis action.yml, step "🚀 Squash-deploy gh-pages", étape 3 — juste après que ce step
# ait cloné gh-pages (ou initialisé un repo vide pour un premier déploiement) et copié dedans le
# contenu fraîchement publié de la branche en cours. La page HTML générée ici est ensuite copiée
# dans ce même clone et incluse dans le commit orphelin poussé sur gh-pages.
#
# Usage : python3 generate-branch-index.py <repo> <current_branch> <branch_dates_json_path> <output_html_path> <canonical_url>
#   repo                 : "owner/repo" du dépôt GitHub (ex. ansforge/interop-ig-portabilite)
#   current_branch       : nom de la branche qui vient d'être publiée par ce run
#   branch_dates_json_path : fichier JSON (dans le clone gh-pages) qui mémorise la date de dernière
#                            publication de chaque branche — nécessaire car gh-pages n'a plus qu'un
#                            seul commit (squash), donc `git log` ne peut plus donner ces dates
#   output_html_path     : chemin où écrire la page HTML générée
#   canonical_url        : URL de la version officielle de l'IG (optionnel, affiche un bandeau si fourni)
import html
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PARIS_TZ = ZoneInfo("Europe/Paris")

# Résout un chemin et vérifie qu'il reste bien à l'intérieur du répertoire de travail courant
# (celui du clone gh-pages), pour éviter d'écrire en dehors de celui-ci si jamais un chemin
# inattendu (ex. "../../etc/passwd") était un jour passé en argument.
def safe_path(path):
    resolved = os.path.realpath(path)
    base_dir = os.path.realpath(os.getcwd())
    if resolved != base_dir and not resolved.startswith(base_dir + os.sep):
        raise ValueError(f"path {path!r} is outside the allowed directory")
    return resolved


repo = sys.argv[1]
current_branch = sys.argv[2]

# branch_dates_path et output_path sont fournis par action.yml (valeurs fixes), jamais par un
# utilisateur externe — on vérifie tout de même qu'ils restent dans le répertoire de travail courant.
branch_dates_path = safe_path(sys.argv[3])
output_path = safe_path(sys.argv[4])

# Canonical URL de l'IG (lue depuis sushi-config.yaml par action.yml) — vide si absente/non trouvée.
canonical_url = sys.argv[5] if len(sys.argv) > 5 else ""

token = os.environ["GITHUB_TOKEN"]

API = "https://api.github.com"


# Petit wrapper autour de l'API REST GitHub : ajoute l'authentification, décode le JSON de la
# réponse, et renvoie None sur un 404 (ex. repo/chemin inexistant) au lieu de faire planter l'appelant.
def api_get(path):
    req = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def load_branch_dates():
    # Seule source de date par branche depuis le squash de gh-pages à 1 commit (git log ne suffit plus).
    try:
        with open(branch_dates_path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def find_branches(path=""):
    """Descend récursivement dans gh-pages jusqu'à trouver les dossiers de branches.

    Les noms de branches peuvent contenir des "/" (ex. "feat/ma-feature"), ce qui crée des
    niveaux de répertoires intermédiaires dans gh-pages — un dossier de premier niveau comme
    "feat/" n'est donc pas forcément une branche. Le dossier "ig/" (toujours créé par l'action
    pour chaque branche publiée) sert de marqueur fiable pour identifier une feuille.
    La racine elle-même n'est jamais une feuille (même si une branche s'appelle littéralement
    "ig", auquel cas on continue de descendre dans ce dossier comme dans les autres).
    """
    listing = api_get(f"/repos/{repo}/contents/{path}?ref=gh-pages" if path else f"/repos/{repo}/contents?ref=gh-pages")
    dirs = [e["name"] for e in (listing or []) if e["type"] == "dir"]
    if path and "ig" in dirs:
        return [path]
    found = []
    for name in dirs:
        found.extend(find_branches(f"{path}/{name}" if path else name))
    return found


stored_dates = load_branch_dates()

try:
    # La branche par défaut du repo (ex. "main") est exposée nativement par l'API GitHub —
    # inutile de la redemander via un input d'action.
    default_branch = api_get(f"/repos/{repo}")["default_branch"]
    branches = {branch_path: stored_dates.get(branch_path) for branch_path in find_branches()}
except Exception as e:
    # Un hoquet de l'API GitHub (rate limit, 5xx, erreur réseau) ne doit pas faire échouer
    # la publication de l'IG pour une simple page de confort : on se rabat sur la branche
    # en cours de build uniquement.
    print(f"::warning::Impossible de lister les branches publiées via l'API GitHub ({e}) — page de listing limitée à la branche courante.", file=sys.stderr)
    default_branch = current_branch
    branches = {}

# La branche en cours de build vient d'être publiée (étape précédente) : on force sa date à "maintenant".
branches[current_branch] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# Persiste le manifeste dans le clone gh-pages — action.yml l'inclura dans le commit orphelin.
stored_dates.update(branches)
with open(branch_dates_path, "w") as f:
    json.dump(stored_dates, f, indent=2, sort_keys=True)

# Ordre d'affichage du tableau : la branche par défaut en premier (si elle a bien été publiée),
# puis les autres branches triées de la plus récemment publiée à la plus ancienne.
others = sorted(
    (name for name in branches if name != default_branch),
    key=lambda name: branches[name] or "",
    reverse=True,
)
ordered = ([default_branch] if default_branch in branches else []) + others


# Convertit une date ISO UTC (ex. "2026-10-20T13:53:25Z") en affichage "JJ/MM/AAAA HH:MM" heure
# de Paris, ou "—" si la branche n'a pas (encore) de date connue.
def fmt(date_str):
    if not date_str:
        return "—"
    dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return dt.astimezone(PARIS_TZ).strftime("%d/%m/%Y %H:%M")


# Une ligne de tableau par branche : lien vers sa preview, nom (avec suffixe "(défaut)" le cas
# échéant) et date formatée. html.escape()/urllib.parse.quote() protègent contre un nom de
# branche contenant des caractères spéciaux HTML ou non valides dans une URL.
rows = "\n".join(
    f'<tr class="{"default" if name == default_branch else ""}">'
    f'<td><a href="./{urllib.parse.quote(name)}/ig/">{html.escape(name)}</a>{" (défaut)" if name == default_branch else ""}</td>'
    f'<td>{fmt(branches[name])}</td>'
    f"</tr>"
    for name in ordered
)

# Bandeau d'avertissement affiché seulement si une URL canonique a été trouvée dans
# sushi-config.yaml : rappelle que ces pages sont des previews de développement et renvoie vers
# la version officielle de l'IG.
notice = (
    f'<p class="notice">⚠️ Ces previews sont des versions de développement (intégration continue), '
    f'générées automatiquement à chaque modification du dépôt, à des fins de consultation uniquement. '
    f'Version officielle publiée (actuelle ou à venir) : '
    f'<a href="{html.escape(canonical_url)}">{html.escape(canonical_url)}</a></p>'
    if canonical_url else ""
)

# Page HTML complète (CSS inline, pas de dépendance externe) : titre, bandeau d'avertissement
# éventuel, puis le tableau des branches dans l'ordre calculé plus haut.
page_html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>{html.escape(repo)} — previews ci-build</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 640px; }}
    th, td {{ text-align: left; padding: 0.5rem 1rem; border-bottom: 1px solid #ddd; }}
    tr.default td {{ font-weight: bold; }}
    .notice {{ background-color: #fff9e6; border-left: 4px solid #ff9800; padding: 0.75rem 1rem; max-width: 640px; }}
  </style>
</head>
<body>
  <h1><a href="https://github.com/{urllib.parse.quote(repo)}">{html.escape(repo)}</a> — previews ci-build</h1>
  {notice}
  <table>
    <thead><tr><th>Branche</th><th>Dernière mise à jour (heure de Paris)</th></tr></thead>
    <tbody>
{rows}
    </tbody>
  </table>
</body>
</html>
"""

# Écrit la page générée à l'emplacement attendu par action.yml (to_publish_root/index.html),
# qui la copiera ensuite à la racine du clone gh-pages.
with open(output_path, "w") as f:
    f.write(page_html)
