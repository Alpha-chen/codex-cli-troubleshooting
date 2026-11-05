#!/usr/bin/env bash
# Installer for the codex-cli-troubleshooting agent skill.
#
#   ./install.sh                       # Hermes Agent, default profile
#   ./install.sh --target codex        # Codex CLI (~/.codex/skills)
#   ./install.sh --target both         # both of the above
#   ./install.sh --path DIR            # explicit skills root (e.g. /opt/hermes/skills)
#   ./install.sh --profile work        # Hermes profile -> ~/.hermes/profiles/work/skills
#   ./install.sh --force               # overwrite an existing install
#
# Also runnable standalone:  curl -fsSL <install.sh url> | bash -s -- --target hermes
set -euo pipefail

NAME="codex-cli-troubleshooting"
VERSION="1.0.1"
ZIP_URL="https://github.com/Alpha-chen/${NAME}/releases/download/v${VERSION}/${NAME}-${VERSION}.zip"

TARGET="hermes"
PROFILE=""
FORCE=0
SKILLS_ROOT=""

say()  { printf '%s\n' "$*"; }
ok()   { printf '  ✓ %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*" >&2; }
die()  { printf '  ✗ %s\n' "$*" >&2; exit 1; }

usage() {
  sed -n '2,16p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//' || true
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --target)  TARGET="${2:-}"; shift 2 || die "--target needs a value" ;;
    --profile) PROFILE="${2:-}"; shift 2 || die "--profile needs a value" ;;
    --path)    SKILLS_ROOT="${2:-}"; shift 2 || die "--path needs a value" ;;
    --force|-f) FORCE=1; shift ;;
    -h|--help) usage ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
done

case "$TARGET" in
  hermes|codex|both) ;;
  *) die "--target must be hermes, codex or both" ;;
esac

command -v python3 >/dev/null 2>&1 || warn "python3 not found — the scripts need it (macOS: brew install python, Linux: apt install python3)"

# ---------------------------------------------------------------- locate source
SELF_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

if [ -n "$SELF_DIR" ] && [ -f "$SELF_DIR/SKILL.md" ]; then
  SRC="$SELF_DIR"
  say "Installing from local files: $SRC"
else
  command -v curl >/dev/null 2>&1 || die "run this from the unzipped folder, or install curl to use the standalone mode"
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  say "Downloading ${NAME} v${VERSION}…"
  curl -fsSL "$ZIP_URL" -o "$TMP/pkg.zip" || die "download failed: $ZIP_URL"
  if command -v unzip >/dev/null 2>&1; then
    unzip -q "$TMP/pkg.zip" -d "$TMP"
  else
    python3 -c 'import sys,zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$TMP/pkg.zip" "$TMP"
  fi
  SRC="$(find "$TMP" -maxdepth 2 -name SKILL.md -print0 | xargs -0 -n1 dirname | head -1)"
  [ -n "$SRC" ] && [ -f "$SRC/SKILL.md" ] || die "archive did not contain SKILL.md"
fi

# ---------------------------------------------------------------- resolve targets
destinations() {
  local roots=()
  if [ -n "$SKILLS_ROOT" ]; then
    roots+=("$SKILLS_ROOT")
  else
    if [ "$TARGET" = "hermes" ] || [ "$TARGET" = "both" ]; then
      local home_skills="${HERMES_HOME:-$HOME/.hermes}"
      [ -n "$PROFILE" ] && home_skills="$home_skills/profiles/$PROFILE"
      roots+=("$home_skills/skills/devops")
    fi
    if [ "$TARGET" = "codex" ] || [ "$TARGET" = "both" ]; then
      roots+=("$HOME/.codex/skills")
    fi
  fi
  printf '%s\n' "${roots[@]}"
}

install_into() {
  local root="$1" dest
  dest="$root/$NAME"

  if [ -e "$dest" ] && [ "$FORCE" -eq 0 ]; then
    die "$dest already exists — re-run with --force to replace it"
  fi
  if [ -e "$dest" ]; then
    local backup="${dest}.bak.$(date +%Y%m%d-%H%M%S)"
    mv "$dest" "$backup"
    ok "existing install moved to $backup"
  fi

  mkdir -p "$dest/scripts"
  cp "$SRC/SKILL.md" "$dest/SKILL.md"
  cp "$SRC"/scripts/*.py "$dest/scripts/"
  [ -f "$SRC/README.md" ] && cp "$SRC/README.md" "$dest/README.md"
  [ -f "$SRC/INSTALL.md" ] && cp "$SRC/INSTALL.md" "$dest/INSTALL.md"
  [ -f "$SRC/LICENSE" ]   && cp "$SRC/LICENSE"   "$dest/LICENSE"
  chmod +x "$dest/scripts/"*.py

  if command -v python3 >/dev/null 2>&1; then
    python3 -m py_compile "$dest"/scripts/*.py || die "scripts failed to compile — install aborted"
    rm -rf "$dest/scripts/__pycache__"
    ok "scripts compile clean"
  fi

  local skill_name skill_desc
  skill_name="$(awk -F': *' '/^name:/{gsub(/"/,"",$2); print $2; exit}' "$dest/SKILL.md")"
  skill_desc="$(awk -F': *' '/^description:/{sub(/^description: */,""); gsub(/^"|"$/,""); print; exit}' "$dest/SKILL.md" | cut -c1-60)"
  [ "$skill_name" = "$NAME" ] || warn "frontmatter name is '$skill_name', expected '$NAME'"

  ok "installed → $dest"
  say "     $skill_name — $skill_desc"
}

while IFS= read -r root; do
  [ -n "$root" ] && install_into "$root"
done < <(destinations)

say ""
say "Done. ${NAME} v${VERSION}"
say "  Trigger it by asking about Codex failures, e.g. \"codex 一直 reconnect\" / \"Selected model is at capacity\"."
say "  Quick self-check:  python3 <installed>/scripts/codex_logs.py"
say "  Uninstall:         rm -rf <installed>"
