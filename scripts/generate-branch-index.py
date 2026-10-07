#python3 generate-branch-index.py <repo> <current_branch> <output_html_path>
import html
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

repo = sys.argv[1]
current_branch = sys.argv[2]

# output_path est fourni par action.yml (valeur fixe "./to_publish_root/index.html"), jamais par
# un utilisateur externe — on vérifie tout de même qu'il reste dans le répertoire de travail courant.
output_path = os.path.abspath(sys.argv[3])
if os.path.commonpath([output_path, os.getcwd()]) != os.getcwd():
    raise ValueError(f"output_path doit rester dans le répertoire de travail courant : {output_path}")

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


def last_update(branch_path):
    commits = api_get(f"/repos/{repo}/commits?path={urllib.parse.quote(branch_path)}&sha=gh-pages&per_page=1")
    if not commits:
        return None
    return commits[0]["commit"]["committer"]["date"]


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


try:
    # La branche par défaut du repo (ex. "main") est exposée nativement par l'API GitHub —
    # inutile de la redemander via un input d'action.
    default_branch = api_get(f"/repos/{repo}")["default_branch"]
    branches = {branch_path: last_update(branch_path) for branch_path in find_branches()}
except Exception as e:
    # Un hoquet de l'API GitHub (rate limit, 5xx, erreur réseau) ne doit pas faire échouer
    # la publication de l'IG pour une simple page de confort : on se rabat sur la branche
    # en cours de build uniquement.
    print(f"::warning::Impossible de lister les branches publiées via l'API GitHub ({e}) — page de listing limitée à la branche courante.", file=sys.stderr)
    default_branch = current_branch
    branches = {}

# La branche en cours de build vient d'être publiée (étape précédente) : on force sa date à "maintenant"
# plutôt que de se fier à l'API, qui peut avoir un léger délai de propagation après le push.
branches[current_branch] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

others = sorted(
    (name for name in branches if name != default_branch),
    key=lambda name: branches[name] or "",
    reverse=True,
)
ordered = ([default_branch] if default_branch in branches else []) + others


def fmt(date_str):
    if not date_str:
        return "—"
    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").strftime("%d/%m/%Y %H:%M UTC")


rows = "\n".join(
    f'<tr class="{"default" if name == default_branch else ""}">'
    f'<td><a href="./{urllib.parse.quote(name)}/ig/">{html.escape(name)}</a>{" (défaut)" if name == default_branch else ""}</td>'
    f'<td>{fmt(branches[name])}</td>'
    f"</tr>"
    for name in ordered
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
  </style>
</head>
<body>
  <h1>{html.escape(repo)} — previews ci-build</h1>
  <table>
    <thead><tr><th>Branche</th><th>Dernière mise à jour</th></tr></thead>
    <tbody>
{rows}
    </tbody>
  </table>
</body>
</html>
"""

with open(output_path, "w") as f:
    f.write(page_html)
