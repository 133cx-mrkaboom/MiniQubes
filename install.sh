#!/usr/bin/env bash
# install.sh - install MiniQubes (CLI, GUI, launcher, desktop session), build the Alpine base system.
#
#   ./install.sh                 install everything (asks for your sudo password when needed)
#   ./install.sh --no-template   skip building the Alpine base system
#   ./install.sh --no-desktop    skip the MiniQubes desktop (labwc + bar); only the CLI/GUI/launcher
#   ./install.sh --dry-run       print what it would do, change nothing
#   ./install.sh --uninstall     remove the programs, session entry, menu entry and desktop shortcut
#   ./install.sh --uninstall --purge   also delete base systems and all qubes (asks first)
#
# Run it from the folder with the MiniQubes files (miniqubes, miniqubes-gui, mq-launcher, mq-menu,
# mq-run, mq-running, mq-tui, miniqubes-session, desktop/), as your normal user (not root).
# Supports x86_64 Arch-, Debian/Ubuntu-, Fedora- and openSUSE-based distros.

set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
OS_RELEASE=${OS_RELEASE:-/etc/os-release}
BIN=/usr/local/bin
TEMPLATES=/var/lib/miniqubes/templates
SHARE=/usr/local/share/miniqubes
SESSION_FILE=/usr/share/wayland-sessions/miniqubes.desktop
PROGS="miniqubes miniqubes-gui mq-launcher mq-clipsync mq-settings mq-quick mq-ws mq-running mq-run mq-menu mq-tui mq-logout mq-profile miniqubes-session"
DRY=0 NO_TEMPLATE=0 NO_DESKTOP=0 UNINSTALL=0 PURGE=0

for a in "$@"; do
  case $a in
    --dry-run) DRY=1 ;;
    --no-template) NO_TEMPLATE=1 ;;
    --no-desktop) NO_DESKTOP=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --purge) PURGE=1 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown option: $a (try --help)" >&2; exit 1 ;;
  esac
done

say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m !!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m xx\033[0m %s\n' "$*" >&2; exit 1; }
run()  { if (( DRY )); then echo "  + $*"; else "$@"; fi; }

(( DRY )) || [ "$EUID" -ne 0 ] || die "run this as your normal user, not root (it uses sudo when it needs to)"
command -v sudo >/dev/null || (( DRY )) || die "sudo is required"

DESKTOP_DIR=$( (xdg-user-dir DESKTOP 2>/dev/null) || echo "$HOME/Desktop")
APPS_DIR=$HOME/.local/share/applications
ICON_DIR=$HOME/.local/share/icons/hicolor/scalable/apps

detect() {
  # shellcheck disable=SC1090
  . "$OS_RELEASE"
  local ids=" ${ID:-} ${ID_LIKE:-} "
  case $ids in
    *" nixos "*) echo nix ;;
    *" arch "*) echo arch ;;
    *" debian "*|*" ubuntu "*) echo debian ;;
    *" fedora "*|*" rhel "*) echo fedora ;;
    *" suse "*|*" opensuse "*) echo suse ;;
    *) echo unknown ;;
  esac
}

# ------------------------------------------------------------------ uninstall
if (( UNINSTALL )); then
  say "removing MiniQubes program files"
  for f in $PROGS; do run sudo rm -f "$BIN/$f"; done
  run sudo rm -rf "$SHARE"
  run sudo rm -f "$SESSION_FILE" "${SESSION_FILE%.desktop}-software.desktop"
  run rm -f "$APPS_DIR/miniqubes.desktop" "$ICON_DIR/miniqubes.svg" "$DESKTOP_DIR/MiniQubes.desktop"
  if (( PURGE )); then
    if (( ! DRY )) && findmnt -R "$TEMPLATES" >/dev/null 2>&1; then
      die "something is still mounted under $TEMPLATES (an admin shell left open?). Close it, run: sudo umount -R $TEMPLATES/*, then retry"
    fi
    read -r -p "Delete ALL base systems and ALL qubes with their data? type 'delete' to confirm: " c
    [ "$c" = delete ] || die "cancelled"
    run sudo rm -rf /var/lib/miniqubes
    run rm -rf "$HOME/.config/miniqubes" "$HOME/.local/share/miniqubes"
  else
    say "kept your base systems and qubes (use --uninstall --purge to delete them too)"
  fi
  say "done"
  exit 0
fi

# ------------------------------------------------------------------ checks
for f in $PROGS; do [ -f "$HERE/$f" ] || die "put install.sh in the same folder as the MiniQubes files (missing: $f)"; done
[ -f "$HERE/mq-patch.py" ] || die "missing mq-patch.py next to install.sh"
[ -f "$HERE/desktop/rc.xml" ] && [ -f "$HERE/desktop/waybar.json" ] || die "missing the 'desktop' folder next to install.sh (needs rc.xml, waybar.json, waybar.css, autostart, environment, version)"
[ "$(uname -m)" = x86_64 ] || die "MiniQubes currently supports x86_64 only (this is $(uname -m))"

DISTRO=$(detect)
say "detected: $DISTRO family ($(. "$OS_RELEASE"; echo "${PRETTY_NAME:-$ID}"))"

# ------------------------------------------------------------------ dependencies
# desktop = labwc (compositor), waybar (bar), swaybg (wallpaper), Qt Wayland plugin, a font,
# nmtui (wi-fi screen), pulsemixer (audio screen) and power-profiles-daemon (battery menu) for the bar buttons
ARCH_PKGS="python bubblewrap pyside6 foot"
(( NO_DESKTOP )) || ARCH_PKGS="$ARCH_PKGS labwc waybar swaybg qt6-wayland ttf-dejavu networkmanager pulsemixer power-profiles-daemon python-gobject passt nftables copyq fuzzel"
# installs each package on its own so one that doesn't exist on this release doesn't stop the rest
each() { local mgr=$1; shift; local p; for p in "$@"; do run $mgr "$p" || warn "couldn't install $p"; done; }

case $DISTRO in
  arch)
    # 1. Is pacman itself healthy? A half-updated system breaks it ("symbol lookup error ... libcurl").
    if command -v pacman >/dev/null && ! (( DRY )) && ! pacman -V >/dev/null 2>&1; then
      warn "pacman is broken on this machine: $(pacman -V 2>&1 | head -1)"
      if [ -f "$HERE/fix-pacman.sh" ]; then
        say "running fix-pacman.sh to repair it"
        bash "$HERE/fix-pacman.sh"
      else
        die "put fix-pacman.sh next to install.sh, run:  sudo bash fix-pacman.sh   then run this again"
      fi
    fi
    # 2. Install ONLY what's missing, and never touch core packages like curl or tar. Arch needs full
    #    upgrades (partial ones are what break systems), so -Syu; pacman asks you to confirm.
    if command -v pacman >/dev/null; then
      missing=$(pacman -T $ARCH_PKGS 2>/dev/null || true)
    else
      missing="$ARCH_PKGS"
    fi
    if [ -n "$missing" ]; then
      say "installing: $missing  (pacman upgrades the system first and asks you to confirm)"
      # shellcheck disable=SC2086
      run sudo pacman -Syu --needed $missing
    else
      say "required packages are already installed"
    fi ;;
  debian)
    run sudo apt-get update
    run sudo apt-get install -y python3 python3-pip bubblewrap curl tar \
        python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets \
      || warn "couldn't install PySide6 from apt (older release?); will try pip below"
    run sudo apt-get install -y foot || run sudo apt-get install -y xterm || true
    (( NO_DESKTOP )) || each "sudo apt-get install -y" labwc waybar swaybg qt6-wayland fonts-dejavu-core network-manager pulsemixer power-profiles-daemon python3-gi passt nftables copyq fuzzel ;;
  fedora)
    run sudo dnf install -y python3 python3-pip bubblewrap python3-pyside6 curl tar \
      || warn "couldn't install PySide6 from dnf; will try pip below"
    run sudo dnf install -y foot || run sudo dnf install -y xterm || true
    (( NO_DESKTOP )) || each "sudo dnf install -y" labwc waybar swaybg qt6-qtwayland dejavu-sans-fonts NetworkManager-tui pulsemixer power-profiles-daemon python3-gobject passt nftables CopyQ fuzzel ;;
  suse)
    run sudo zypper --non-interactive install python3 python3-pip bubblewrap curl tar
    run sudo zypper --non-interactive install python3-pyside6 \
      || warn "couldn't install PySide6 from zypper; will try pip below"
    run sudo zypper --non-interactive install foot || run sudo zypper --non-interactive install xterm || true
    (( NO_DESKTOP )) || each "sudo zypper --non-interactive install" labwc waybar swaybg qt6-wayland dejavu-fonts NetworkManager pulsemixer power-profiles-daemon python3-gobject passt nftables copyq fuzzel ;;
  nix)
    die "NixOS can't be set up by a script like this. Add python3, bubblewrap, python3Packages.pyside6, foot, labwc, waybar and swaybg to your configuration, then copy the MiniQubes files onto your PATH." ;;
  *)
    die "unrecognised distro. Install by hand: python 3.11+, bubblewrap, PySide6, a terminal (foot/kitty/xterm), then copy the two files into /usr/local/bin." ;;
esac

if ! (( DRY )); then
  /usr/bin/python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' \
    || die "Python 3.11 or newer is required (this system has $(/usr/bin/python3 -V)). Use a newer distro release."
  if ! /usr/bin/python3 -c 'import PySide6.QtWidgets' 2>/dev/null; then
    warn "PySide6 not found; trying pip (installs for your user only)"
    /usr/bin/python3 -m pip install --user --break-system-packages PySide6 \
      || die "couldn't get PySide6. Install it (package name varies: pyside6 / python3-pyside6) and run this again."
  fi
fi

# ------------------------------------------------------------------ install the program
# updates to your own copies of miniqubes / miniqubes-gui (wayland socket fix, colored frame on by default,
# the "internet (no LAN)" network mode). Safe to repeat; your other edits are kept.
if (( DRY )); then echo "  + python3 mq-patch.py (update your miniqubes / miniqubes-gui copies)"
else /usr/bin/python3 "$HERE/mq-patch.py" "$HERE" || warn "some updates couldn't be applied automatically (see above)"; fi

say "installing the MiniQubes programs to $BIN"
for f in $PROGS; do run sudo install -m755 "$HERE/$f" "$BIN/$f"; done

if ! (( NO_DESKTOP )); then
  say "installing the MiniQubes desktop (defaults go to $SHARE, your editable copy to ~/.config/miniqubes/desktop)"
  run sudo install -d "$SHARE/desktop"
  for f in "$HERE"/desktop/*; do
    if [ "$(basename "$f")" = autostart ]; then run sudo install -m755 "$f" "$SHARE/desktop/"
    else run sudo install -m644 "$f" "$SHARE/desktop/"; fi
  done
  # power modes (battery button): turn the service on unless another power manager is in charge
  if command -v systemctl >/dev/null 2>&1; then
    if command -v tlp >/dev/null 2>&1 || command -v auto-cpufreq >/dev/null 2>&1; then
      warn "TLP/auto-cpufreq detected: not enabling power-profiles-daemon (the battery power-mode menu won't work)"
    else
      run sudo systemctl enable --now power-profiles-daemon.service || warn "couldn't start power-profiles-daemon (the battery power-mode menu needs it)"
    fi
  fi
  run sudo install -d /usr/share/wayland-sessions
  if ! (( DRY )); then
    sudo tee "$SESSION_FILE" >/dev/null <<EOF
[Desktop Entry]
Name=MiniQubes
Comment=Small desktop where every app runs inside a qube
Exec=$BIN/miniqubes-session
Type=Application
DesktopNames=labwc;wlroots
EOF
    # stop bars/helpers left over from older sessions (skipped if you are running this inside the desktop)
    [ -n "${LABWC_PID:-}" ] || "$BIN/miniqubes-session" --cleanup || true
    sudo tee "${SESSION_FILE%.desktop}-software.desktop" >/dev/null <<EOF
[Desktop Entry]
Name=MiniQubes (software rendering)
Comment=Same desktop, for old PCs / graphics that won't start
Exec=$BIN/miniqubes-session --software
Type=Application
DesktopNames=labwc;wlroots
EOF
    "$BIN/miniqubes-session" --seed
  else
    echo "  + write $SESSION_FILE and seed ~/.config/miniqubes/desktop"
  fi
fi

# can this system make the sandboxes? (needs unprivileged user namespaces)
if ! (( DRY )); then
  if ! err=$(bwrap --unshare-user --ro-bind / / true 2>&1); then
    warn "bubblewrap can't create sandboxes on this system: $err"
    warn "  Ubuntu 24.04+:  sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0"
    warn "  Debian/hardened kernels:  sudo sysctl -w kernel.unprivileged_userns_clone=1"
    warn "  (make it permanent in /etc/sysctl.d/ once you've checked it fixes this)"
  fi
fi

# ------------------------------------------------------------------ menu entry + desktop shortcut
say "adding MiniQubes to your app menu and desktop"
run mkdir -p "$APPS_DIR" "$ICON_DIR"
if ! (( DRY )); then
  cat > "$ICON_DIR/miniqubes.svg" <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#1f2430"/>
  <rect x="10" y="10" width="20" height="20" rx="4" fill="#2e7d32"/>
  <rect x="34" y="10" width="20" height="20" rx="4" fill="#1565c0"/>
  <rect x="10" y="34" width="20" height="20" rx="4" fill="#c62828"/>
  <rect x="34" y="34" width="20" height="20" rx="4" fill="#6a1b9a"/>
</svg>
EOF
  cat > "$APPS_DIR/miniqubes.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=MiniQubes
Comment=Sandboxed app boxes (qubes)
Exec=$BIN/miniqubes-gui
Icon=miniqubes
Terminal=false
Categories=System;Security;
EOF
  command -v update-desktop-database >/dev/null && update-desktop-database "$APPS_DIR" 2>/dev/null || true
  if [ -d "$DESKTOP_DIR" ]; then
    cp "$APPS_DIR/miniqubes.desktop" "$DESKTOP_DIR/MiniQubes.desktop"
    chmod +x "$DESKTOP_DIR/MiniQubes.desktop"
    command -v gio >/dev/null && gio set "$DESKTOP_DIR/MiniQubes.desktop" metadata::trusted true 2>/dev/null || true
  fi
fi

# ------------------------------------------------------------------ base system + first qube
if (( NO_TEMPLATE )); then
  say "skipping base system (--no-template). Build it later from the app, or: miniqubes template build alpine"
elif [ -d "$TEMPLATES/alpine" ]; then
  say "Alpine base system already exists, leaving it alone"
  say "adding wl-clipboard to it (shared clipboard)"
  run miniqubes template install alpine wl-clipboard || warn "couldn't add wl-clipboard; run: miniqubes template install alpine wl-clipboard"
else
  say "building the Alpine base system (downloads ~100 MB, asks for your sudo password)"
  run miniqubes template build alpine
  say "adding the colored-window helper (labwc) and a terminal (foot) to it"
  run miniqubes template install alpine labwc foot wl-clipboard
fi

if ! (( DRY )) && ! compgen -G "$HOME/.config/miniqubes/boxes/*.toml" >/dev/null && [ -d "$TEMPLATES/alpine" ]; then
  say "creating your first qube, 'everyday'"
  miniqubes create everyday --preset alpine
fi

say "all done."
if (( NO_DESKTOP )); then
  say "open MiniQubes from your app menu or the desktop icon (or run: miniqubes-gui), inside any Wayland session"
else
  say "try the MiniQubes desktop right now, in a window on your current desktop:   miniqubes-session"
  say "  (old PC or black screen? use:  miniqubes-session --software)"
  say "to use it for real: log out and pick 'MiniQubes' (SDDM/GDM session list; the "software rendering" one is for old PCs), or at a text console"
  say "  (Ctrl+Alt+F2) log in and run:  miniqubes-session"
  say "inside it: click the green Launcher button (or Super+Space) -> hover a qube -> pick an app.  Super+M = manager, Super+P = power."
  say "desktop settings: ~/.config/miniqubes/desktop  (new versions replace them automatically and keep a backup; --reset restores defaults)"
fi
