#!/usr/bin/env bash
# fix-pacman.sh - repair pacman when it dies with "symbol lookup error ... libcurl.so.4 ... ngtcp2_..."
# (a half-updated Arch system), then do a proper full upgrade.
#
#   sudo bash fix-pacman.sh                  # fixes ngtcp2 (the usual culprit)
#   sudo bash fix-pacman.sh ngtcp2 nghttp3   # or name the package(s) from the error message
#
# Where the fixed package comes from, in order:
#   1. a package file next to this script (e.g. ngtcp2-1.x-1-x86_64.pkg.tar.zst copied from a working Arch PC:
#        cp "$(ls -v /var/cache/pacman/pkg/ngtcp2-[0-9]*.pkg.tar.zst | tail -1)" ~/miniqubes/ )
#   2. a download from the Arch mirror using python3 (no libcurl needed)

set -euo pipefail
[ "$EUID" -eq 0 ] || exec sudo bash "$0" "$@"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PKGS=("$@"); [ ${#PKGS[@]} -gt 0 ] || PKGS=(ngtcp2)

for pkg in "${PKGS[@]}"; do
  file=""
  local_file=$(ls -v "$HERE/$pkg"-[0-9]*.pkg.tar.zst 2>/dev/null | tail -1 || true)
  if [ -n "$local_file" ]; then
    echo "==> using $(basename "$local_file") from this folder"
    file=$local_file
  elif command -v python3 >/dev/null; then
    echo "==> downloading latest $pkg from the Arch mirror"
    PKG=$pkg python3 - <<'EOF'
import os, re, urllib.request
pkg = os.environ["PKG"]
for repo in ("core", "extra"):
    base = f"https://geo.mirror.pkgbuild.com/{repo}/os/x86_64/"
    try:
        html = urllib.request.urlopen(base, timeout=30).read().decode()
    except Exception:
        continue
    names = set(re.findall(r'href="(' + re.escape(pkg) + r'-\d[^"/]*-x86_64\.pkg\.tar\.zst)"', html))
    if names:
        key = lambda s: [int(x) for x in re.findall(r"\d+", s[len(pkg) + 1:].split("-x86_64")[0])]
        n = max(names, key=key)
        print("   downloading", n)
        if not os.environ.get("DRY"):
            urllib.request.urlretrieve(base + n, f"/tmp/{pkg}.pkg.tar.zst")
        break
else:
    raise SystemExit(f"couldn't find {pkg} on the mirror")
EOF
    file=/tmp/$pkg.pkg.tar.zst
  else
    echo "no python3 here and no $pkg package file next to this script." >&2
    echo "On a working Arch PC run:" >&2
    echo "  sudo pacman -Sw --noconfirm $pkg" >&2
    echo "  cp \"\$(ls -v /var/cache/pacman/pkg/$pkg-[0-9]*.pkg.tar.zst | tail -1)\" ~/miniqubes/" >&2
    echo "then copy that file next to fix-pacman.sh on this PC and run it again." >&2
    exit 1
  fi
  if [ -z "${DRY:-}" ]; then
    echo "==> unpacking $pkg"
    tar --zstd -xf "$file" -C / --exclude=.PKGINFO --exclude=.MTREE --exclude=.BUILDINFO --exclude=.INSTALL
  fi
done

[ -z "${DRY:-}" ] || exit 0
echo "==> checking pacman works"
pacman -Q "${PKGS[@]}"
echo "==> full system upgrade (pacman will ask you to confirm)"
pacman -Syu
echo "==> done"
