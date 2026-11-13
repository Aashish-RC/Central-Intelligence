#!/usr/bin/env bash
# Central Intelligence: read-only, bounded repository and Codespaces audit.
set -uo pipefail
umask 077
ROOT="${1:-$PWD}"
ROOT="$(cd "$ROOT" 2>/dev/null && pwd -P)" || { echo 'Repository directory not found'; exit 2; }
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${TMPDIR:-/tmp}/CI-Audit-${STAMP}"
mkdir -p "$OUT"
REPORT="$OUT/REPORT.md"
exec > >(tee "$REPORT") 2>&1
section(){ printf '\n## %s\n\n' "$1"; }
run(){ local label="$1"; shift; printf '\n### %s\n\n```text\n' "$label"; timeout 20s "$@" 2>&1 | head -n 100 || true; printf '\n```\n'; }
exists(){ [[ -e "$ROOT/$1" ]] && echo "PRESENT $1" || echo "ABSENT $1"; }
cd "$ROOT" || exit 2
printf '# Central Intelligence read-only audit\n\nUTC: %s\n\n' "$(date -u +%FT%TZ)"
echo 'Scope: metadata, repository inventory, build/test declarations, CI, Docker configuration names. No tests, installs, Docker starts, pushes or model calls.'
section 'Runtime and resources'
run 'System' uname -a
run 'CPU and memory' bash -c 'nproc; free -h; df -h .'
run 'Tool versions' bash -c 'for c in git gh opencode docker node npm pnpm python3 pytest; do if command -v "$c" >/dev/null; then printf "%s: " "$c"; case "$c" in python3) "$c" --version;; docker) "$c" --version;; *) "$c" --version 2>&1 | head -n 1;; esac; else echo "$c: MISSING"; fi; done'
run 'Docker daemon' docker info --format 'Server={{.ServerVersion}} CPUs={{.NCPU}} Memory={{.MemTotal}}'
section 'Git and GitHub'
run 'Git status' git status --short --branch
run 'Tracked file count' bash -c 'git ls-files | wc -l'
run 'Latest commits' git log -8 --date=short --pretty=format:'%h %ad %s'
run 'GitHub authentication' gh auth status
run 'Recent CI runs' gh run list --limit 12 --json databaseId,workflowName,status,conclusion,headBranch,createdAt --jq '.[] | [.databaseId,.workflowName,.status,.conclusion,.headBranch,.createdAt] | @tsv'
section 'Repository layout'
run 'Top-level entries' bash -c 'find . -mindepth 1 -maxdepth 1 -not -name .git -printf "%f\n" | sort'
run 'Directory layout (depth 3)' bash -c 'find . -maxdepth 3 -type d \( -name .git -o -name node_modules -o -name .venv -o -name dist -o -name build \) -prune -o -type d -print | head -n 180'
run 'Tracked file extensions' bash -c 'git ls-files | awk -F. '\''NF>1 {print $NF}'\'' | sort | uniq -c | sort -nr | head -n 35'
section 'Architecture and documentation'
run 'Documentation paths' bash -c 'git ls-files "docs/**" | head -n 180'
run 'Architecture-related filenames' bash -c 'git ls-files | grep -Ei "(^|/)(layer|architecture|roadmap|design|requirements|adr|milestone|plan)" | head -n 140 || true'
section 'Project manifests (safe summaries)'
if [[ -f package.json ]]; then
  run 'Node package metadata and scripts' node -e 'const p=require("./package.json"); console.log(JSON.stringify({name:p.name,packageManager:p.packageManager,workspaces:p.workspaces,scripts:p.scripts},null,2))'
fi
if [[ -f pyproject.toml ]]; then
  run 'Python metadata, without credentials' python3 -c 'import tomllib; p=tomllib.load(open("pyproject.toml","rb")); print("project:",p.get("project",{}).get("name")); print("requires-python:",p.get("project",{}).get("requires-python")); print("dependency names:",len(p.get("project",{}).get("dependencies",[]))); print("pytest config present:","pytest" in p.get("tool",{}))'
fi
run 'Dependency/config file presence' bash -c 'for f in package.json pnpm-lock.yaml package-lock.json turbo.json pyproject.toml requirements.txt requirements.lock Dockerfile docker-compose.yml .devcontainer/devcontainer.json AGENTS.md opencode.json .github/dependabot.yml .github/CODEOWNERS; do test -e "$f" && echo "PRESENT $f" || echo "ABSENT $f"; done'
section 'Tests and build declarations'
run 'Test paths' bash -c 'git ls-files | grep -Ei "(^|/)(tests?|__tests__)/|(_test|\.test|\.spec)\.(py|ts|tsx|js|jsx)$" | head -n 180 || true'
run 'CI workflow filenames' bash -c 'git ls-files ".github/workflows/**"'
run 'Package workspace manifests' bash -c 'git ls-files "**/package.json" | head -n 90'
section 'Docker and integration services'
run 'Compose services (without environment expansion)' bash -c 'if test -f docker-compose.yml; then grep -E "^  [a-zA-Z0-9_-]+:" docker-compose.yml | head -n 90; fi'
run 'Compose referenced variable names (no values)' bash -c 'if test -f docker-compose.yml; then grep -oE '\''\$\{[A-Za-z_][A-Za-z0-9_]*'\'' docker-compose.yml | sed '\''s/^\${//'\'' | sort -u; fi'
section 'Agent and security integration'
run 'Agent/skill files' bash -c 'git ls-files | grep -Ei "(^|/)(AGENTS\.md|opencode\.jsonc?|\.opencode/|\.agents/|\.github/agents/|\.github/ISSUE_TEMPLATE/|\.github/PULL_REQUEST_TEMPLATE)" | head -n 90 || true'
run 'Security tool availability' bash -c 'for c in gitleaks trivy semgrep ruff mypy; do command -v "$c" >/dev/null && echo "$c: FOUND" || echo "$c: MISSING"; done'
section 'Notes and limitations'
echo '- This audit does not establish that tests pass, that model calls succeed, or that release is ready.'
echo '- GitHub access may be limited by the Codespace token permissions.'
echo '- Filenames, commit subjects, directory names and GitHub run metadata may be sensitive; review before sharing.'
echo '- A complete architecture traceability assessment requires reading source and docs separately.'
# End tee before archive, ensure report is fully written.
sleep 1
printf '\nReport directory: %s\n' "$OUT"
printf 'Report file: %s\n' "$REPORT"
printf 'To share: upload REPORT.md from the above directory.\n'
