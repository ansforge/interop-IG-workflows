#python3 generate-branch-index.py <repo> <current_branch> <output_html_path>
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

repo = sys.argv[1]
current_branch = sys.argv[2]
output_path = sys.argv[3]
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
    """
    listing = api_get(f"/repos/{repo}/contents/{path}?ref=gh-pages" if path else f"/repos/{repo}/contents?ref=gh-pages")
    dirs = [e["name"] for e in (listing or []) if e["type"] == "dir"]
    if "ig" in dirs:
        return [path] if path else []
    found = []
    for name in dirs:
        found.extend(find_branches(f"{path}/{name}" if path else name))
    return found


# La branche par défaut du repo (ex. "main") est exposée nativement par l'API GitHub —
# inutile de la redemander via un input d'action.
default_branch = api_get(f"/repos/{repo}")["default_branch"]

branches = {branch_path: last_update(branch_path) for branch_path in find_branches()}

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
    f'<td><a href="./{name}/ig/">{name}</a>{" (défaut)" if name == default_branch else ""}</td>'
    f'<td>{fmt(branches[name])}</td>'
    f"</tr>"
    for name in ordered
)

html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>{repo} — previews ci-build</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 640px; }}
    th, td {{ text-align: left; padding: 0.5rem 1rem; border-bottom: 1px solid #ddd; }}
    tr.default td {{ font-weight: bold; }}
  </style>
</head>
<body>
  <h1>{repo} — previews ci-build</h1>
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
    f.write(html)
