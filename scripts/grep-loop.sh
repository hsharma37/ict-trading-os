#!/usr/bin/env bash
set -euo pipefail

base_ref="${1:-origin/dev}"

if ! command -v rg >/dev/null 2>&1; then
  echo "ripgrep is required for grep-loop" >&2
  exit 127
fi

if git rev-parse --verify "$base_ref" >/dev/null 2>&1; then
  changed_files="$(git diff --name-only "$base_ref"...HEAD)"
else
  changed_files="$(git diff --name-only HEAD~1...HEAD 2>/dev/null || git ls-files)"
fi

untracked_files="$(git ls-files --others --exclude-standard)"
changed_files="$(printf '%s\n%s\n' "$changed_files" "$untracked_files" | sed '/^$/d' | sort -u)"

if [ -z "$changed_files" ]; then
  echo "grep-loop: no changed files to scan"
  exit 0
fi

scan_files="$(printf '%s\n' "$changed_files" | rg -v '(^|/)(node_modules|\.venv|\.rizz|frontend/dist|\.vercel)/|^scripts/grep-loop\.sh$|(\.png|\.jpg|\.jpeg|\.gif|\.webp|\.pdf|\.lock|\.db|\.sqlite|\.sqlite3)$' || true)"

if [ -z "$scan_files" ]; then
  echo "grep-loop: changed files are all generated/binary/ignored"
  exit 0
fi

tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT
printf '%s\n' "$scan_files" > "$tmpfile"

status=0

run_rg() {
  xargs rg "$@" < "$tmpfile"
}

echo "grep-loop: scanning changed source/docs files"

if run_rg -n --pcre2 '(postgres(ql)?://[^[:space:]'"'"'"]+:[^[:space:]'"'"'"]+@|gho_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{20,}|SUPABASE_(SERVICE_ROLE|JWT_SECRET)|BEGIN (RSA|OPENSSH) PRIVATE KEY)'; then
  echo "grep-loop: potential secret material found" >&2
  status=1
fi

if run_rg -n 'AUTH_ENABLED\s*=\s*["'\"']?false|CORS_ORIGINS\s*=\s*["'\"']?\*|allow_origins\s*=\s*\["\*"\]'; then
  echo "grep-loop: auth/CORS relaxation touched; justify it in the PR body" >&2
  status=1
fi

if run_rg -n --glob '!*.md' 'print\(|console\.log\(|TODO|FIXME|pass\s*(#.*)?$'; then
  echo "grep-loop: debug/TODO/pass marker touched; remove or justify it" >&2
  status=1
fi

if run_rg -n --glob '!*.md' 'Math\.random\(|round\([^,\n]+,\s*[26]\)|time\.time\(\)'; then
  echo "grep-loop: trading-sensitive randomness, rounding, or timestamp pattern touched; verify safety" >&2
  status=1
fi

if run_rg -n 'dangerouslySetInnerHTML|innerHTML|eval\(|new Function\('; then
  echo "grep-loop: unsafe rendering/eval pattern touched" >&2
  status=1
fi

if [ "$status" -eq 0 ]; then
  echo "grep-loop: clean"
fi

exit "$status"
