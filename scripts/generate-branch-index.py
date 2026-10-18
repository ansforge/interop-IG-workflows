#python3 generate-branch-index.py <repo> <current_branch> <branch_dates_json_path> <output_html_path> <canonical_url>
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
    """Charge le manifeste des dates de dernière publication par branche.

    Depuis le passage au squash de gh-pages (1 seul commit par run), `git log` ne permet plus
    de retrouver la date de publication de chaque branche individuellement — ce manifeste est
    la seule source de vérité, maintenue par action.yml (lu depuis le clone gh-pages avant le
    squash, réécrit après chaque run) et persisté dans le commit orphelin.
    """
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

# Persiste le manifeste (mis à jour pour la branche courante, préservé pour les autres) dans le
# clone gh-pages — action.yml l'inclura dans le commit orphelin du squash.
stored_dates.update(branches)
with open(branch_dates_path, "w") as f:
    json.dump(stored_dates, f, indent=2, sort_keys=True)

others = sorted(
    (name for name in branches if name != default_branch),
    key=lambda name: branches[name] or "",
    reverse=True,
)
ordered = ([default_branch] if default_branch in branches else []) + others


def fmt(date_str):
    if not date_str:
        return "—"
    dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return dt.astimezone(PARIS_TZ).strftime("%d/%m/%Y %H:%M")


rows = "\n".join(
    f'<tr class="{"default" if name == default_branch else ""}">'
    f'<td><a href="./{urllib.parse.quote(name)}/ig/">{html.escape(name)}</a>{" (défaut)" if name == default_branch else ""}</td>'
    f'<td>{fmt(branches[name])}</td>'
    f"</tr>"
    for name in ordered
)

notice = (
    f'<p class="notice">⚠️ Ces previews sont des versions de développement (intégration continue), '
    f'générées automatiquement à chaque modification du dépôt, à des fins de consultation uniquement. '
    f'Version officielle publiée (actuelle ou à venir) : '
    f'<a href="{html.escape(canonical_url)}">{html.escape(canonical_url)}</a></p>'
    if canonical_url else ""
)

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

with open(output_path, "w") as f:
    f.write(page_html)
