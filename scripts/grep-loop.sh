#!/usr/bin/env bash
set -euo pipefail

base_ref="${1:-origin/dev}"

if ! command -v rg >/dev/null 2>&1; then
  echo "ripgrep is required for grep-loop" >&2
  exit 127
fi

if [[ "$base_ref" == origin/* ]]; then
  git fetch --no-tags --depth=1 origin "${base_ref#origin/}:refs/remotes/${base_ref}" >/dev/null 2>&1 || true
fi

if ! git rev-parse --verify "$base_ref" >/dev/null 2>&1 && [[ "$base_ref" == origin/* ]]; then
  git fetch --no-tags origin "${base_ref#origin/}:refs/remotes/${base_ref}" >/dev/null 2>&1 || true
fi

if git rev-parse --verify "$base_ref" >/dev/null 2>&1; then
  changed_files="$(git diff --name-only "$base_ref"...HEAD)"
else
  changed_files="$(git diff --name-only HEAD~1...HEAD 2>/dev/null || git ls-files)"
fi

untracked_files=""
if [ "${CI:-}" != "true" ]; then
  untracked_files="$(git ls-files --others --exclude-standard)"
fi
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
diff_tmp="$(mktemp)"
untracked_tmp="$(mktemp)"
trap 'rm -f "$tmpfile" "$diff_tmp" "$untracked_tmp"' EXIT
printf '%s\n' "$scan_files" > "$tmpfile"
: > "$untracked_tmp"
if [ -n "$untracked_files" ]; then
  printf '%s\n' "$untracked_files" | rg -v '(^|/)(node_modules|\.venv|\.rizz|frontend/dist|\.vercel)/|^scripts/grep-loop\.sh$|(\.png|\.jpg|\.jpeg|\.gif|\.webp|\.pdf|\.lock|\.db|\.sqlite|\.sqlite3)$' > "$untracked_tmp" || true
fi

tracked_scan_files="$(comm -23 <(sort "$tmpfile") <(sort "$untracked_tmp") || true)"
if [ -n "$tracked_scan_files" ]; then
  if git rev-parse --verify "$base_ref" >/dev/null 2>&1; then
    printf '%s\n' "$tracked_scan_files" | xargs git diff --unified=0 "$base_ref"...HEAD -- \
      | awk '/^\+[^+]/ {sub(/^\+/, ""); print}' > "$diff_tmp"
  else
    printf '%s\n' "$tracked_scan_files" | xargs git diff --unified=0 HEAD~1...HEAD -- 2>/dev/null \
      | awk '/^\+[^+]/ {sub(/^\+/, ""); print}' > "$diff_tmp" || true
  fi
fi

status=0

run_added_rg() {
  local pattern="$1"
  if [ -s "$diff_tmp" ] && rg -n --pcre2 "$pattern" "$diff_tmp"; then
    return 0
  fi
  if [ -s "$untracked_tmp" ] && xargs rg -n --pcre2 "$pattern" < "$untracked_tmp"; then
    return 0
  fi
  return 1
}

echo "grep-loop: scanning added source/docs lines"

if run_added_rg '(postgres(ql)?://[^[:space:]'"'"'"]+:[^[:space:]'"'"'"]+@|gho_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{20,}|SUPABASE_(SERVICE_ROLE|JWT_SECRET)|BEGIN (RSA|OPENSSH) PRIVATE KEY)'; then
  echo "grep-loop: potential secret material found" >&2
  status=1
fi

if run_added_rg 'AUTH_ENABLED\s*=\s*["'\"']?false|CORS_ORIGINS\s*=\s*["'\"']?\*|allow_origins\s*=\s*\["\*"\]'; then
  echo "grep-loop: auth/CORS relaxation touched; justify it in the PR body" >&2
  status=1
fi

if run_added_rg 'print\(|console\.log\(|TODO|FIXME|pass\s*(#.*)?$'; then
  echo "grep-loop: debug/TODO/pass marker touched; remove or justify it" >&2
  status=1
fi

if run_added_rg 'Math\.random\(|round\([^,\n]+,\s*[26]\)|time\.time\(\)'; then
  echo "grep-loop: trading-sensitive randomness, rounding, or timestamp pattern touched; verify safety" >&2
  status=1
fi

if run_added_rg 'dangerouslySetInnerHTML|innerHTML|eval\(|new Function\('; then
  echo "grep-loop: unsafe rendering/eval pattern touched" >&2
  status=1
fi

if [ "$status" -eq 0 ]; then
  echo "grep-loop: clean"
fi

exit "$status"
