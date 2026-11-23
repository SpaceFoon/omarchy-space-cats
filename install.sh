#!/bin/bash
# Install Space Cats as the Omarchy screensaver. Safe to re-run (that's also how you update).
#
#   ./install.sh             install or update
#   ./install.sh uninstall   remove it and go back to the stock screensaver
#   ./install.sh status      show what is installed
#
# What it touches:
#   ~/.local/share/space-cats/   the animation and two small scripts (copied, so the clone can go)
#   ~/.bashrc                    one marked block near the top that puts ~/.local/share/space-cats/bin
#                                first on PATH, so Omarchy's idle timer finds our launcher first
set -euo pipefail

src=$(dirname "$(readlink -f "$0")")
dest="$HOME/.local/share/space-cats"
rc="$HOME/.bashrc"
begin='# >>> space-cats screensaver >>>'
end='# <<< space-cats screensaver <<<'
stock="${OMARCHY_PATH:-/usr/share/omarchy}/bin/omarchy-launch-screensaver"

say() { printf '%s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

remove_rc_block() {
  [[ -f $rc ]] || return 0
  # also drop the one-line marker used by early versions
  sed -i -e "/^$begin\$/,/^$end\$/d" -e '/^# space-cats screensaver: /,+1d' "$rc"
}

installed_ok() {
  [[ -x $dest/bin/omarchy-launch-screensaver && -x $dest/bin/space-cats-screensaver && -f $dest/space-cats.py ]] &&
    grep -qxF "$begin" "$rc" 2>/dev/null
}

case "${1:-install}" in
uninstall)
  remove_rc_block
  rm -rf "$dest" "${XDG_RUNTIME_DIR:-/tmp}/space-cats"
  rm -f "$HOME/.local/bin/space-cats-screensaver" # left by early versions
  say "Space Cats removed. Omarchy's stock screensaver is back for new shells and the next idle."
  exit 0
  ;;
status)
  if installed_ok; then say "installed in $dest"; else say "not installed"; fi
  [[ -f $stock ]] && grep -q -- '-e omarchy-screensaver' "$stock" &&
    say "Omarchy launcher: compatible" || say "Omarchy launcher: NOT compatible (the stock screensaver will run)"
  exit 0
  ;;
install) ;;
*) die "unknown command '$1' (use: install, uninstall, status)" ;;
esac

# --- checks ---------------------------------------------------------------
[[ -f $stock ]] || die "Omarchy not found ($stock is missing). Space Cats only works on Omarchy."
grep -q -- '-e omarchy-screensaver' "$stock" ||
  die "this Omarchy version's screensaver launcher looks different from what Space Cats expects; not installing."
for cmd in hyprctl jq; do
  command -v "$cmd" >/dev/null || die "'$cmd' is required"
done
python=/usr/bin/python3
[[ -x $python ]] || python=$(command -v python3 || true)
[[ -n $python ]] || die "python3 is required"
"$python" -c 'import sys; sys.exit(sys.version_info < (3, 8))' || die "python 3.8 or newer is required"
case "$(xdg-terminal-exec --print-id 2>/dev/null)" in
*Alacritty* | *ghostty* | *foot* | *kitty*) ;;
*) warn "Omarchy's screensaver only runs in Alacritty, Ghostty, Foot or Kitty; set one as your default terminal." ;;
esac

# --- files ----------------------------------------------------------------
mkdir -p "$dest/bin"
install -m 755 "$src/space-cats.py" "$dest/space-cats.py"
install -m 755 "$src/bin/space-cats-screensaver" "$src/bin/omarchy-launch-screensaver" "$dest/bin/"
rm -f "$HOME/.local/bin/space-cats-screensaver" # left by early versions

# --- PATH -----------------------------------------------------------------
# Omarchy's idle timer starts the screensaver through `bash -lc`, which reads ~/.bashrc.
# The block must sit above the "not interactive? stop here" line, so it goes right after
# Omarchy's env-bootstrap line, or at the very top if that line isn't there.
touch "$rc"
remove_rc_block
cp "$rc" "$rc.space-cats.bak"
block_file=$(mktemp)
printf '%s\n%s\n%s\n' "$begin" 'export PATH="$HOME/.local/share/space-cats/bin:$PATH"' "$end" >"$block_file"
anchor=$(grep -n 'env-bootstrap' "$rc" | head -1 | cut -d: -f1 || true)
if [[ -n $anchor ]]; then
  sed -i "${anchor}r $block_file" "$rc"
else
  cat "$block_file" "$rc" >"$rc.space-cats.tmp" && mv "$rc.space-cats.tmp" "$rc"
fi
rm -f "$block_file"

installed_ok || die "something went wrong; ~/.bashrc was backed up to ~/.bashrc.space-cats.bak"
say "Space Cats installed. It takes over the next time the screensaver starts."
say "Try it now:   bash -lc 'omarchy-launch-screensaver force'"
say "Preview:      $python $dest/space-cats.py   (in any terminal; any key quits)"
