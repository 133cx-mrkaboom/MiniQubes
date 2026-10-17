# MiniQubes

**Qubes-style compartmentalisation without the virtual machines.**

MiniQubes splits your computer into coloured, separate *qubes* (a school qube, a banking qube, a throwaway qube...). Each one is a sandbox with its own files, its own settings and its own idea of what the rest of the system looks like. A bad program in one qube can't just walk into the others.

It runs on plain Linux using [bubblewrap](https://github.com/containers/bubblewrap), the same sandboxing tool Flatpak uses. No hypervisor, no RAM-hungry VMs, apps start instantly.

> **Honest scope:** MiniQubes is for everyday privacy and damage control. It is **not** a replacement for Qubes OS. If a government with real resources is after you, use Qubes OS. See [What it does *not* protect against](#what-it-does-not-protect-against).

---

## Contents

- [Ideology](#ideology)
- [How it works](#how-it-works)
- [Features](#features)
- [Install](#install)
- [Using it](#using-it)
- [Keybinds](#keybinds-desktop-session)
- [Templates (base systems)](#templates-base-systems)
- [Security levels](#security-levels)
- [Networking](#networking)
- [Clipboard, USB, dead man's switch, export/import](#extras)
- [Command line](#command-line)
- [What it does not protect against](#what-it-does-not-protect-against)
- [Uninstall](#uninstall)
- [Contributing and licence](#contributing)

---

## Ideology

1. **Don't let everything see everything.** Normally every program you run can read your browser profile, your SSH keys and your documents. MiniQubes flips that: a program sees only what its qube was given.
2. **Compartments, not perfection.** A compromised browser tab game should not be able to reach your bank session. That is the goal. Full protection against a determined attacker is not.
3. **Light enough to actually use.** If protection costs a VM per task you will stop using it. Qubes here start like normal apps.
4. **Safe defaults, explicit opt-in.** Sound, camera, shared folders, USB drives and clipboard are things you turn on per qube. Network, security level and base system are per qube too.
5. **Understandable.** Small Python and shell scripts you can read in an evening. No daemon, no magic.

## How it works

```
 your real system (host)
 |
 +-- template "alpine"   read-only base system, shared (root-owned, /var/lib/miniqubes/templates)
 +-- template "arch"     another read-only base system
 +-- template "vault"    your own separate base system, for sensitive qubes
 |
 +-- qube "school"   --uses--> alpine   own home folder, blue frame
 +-- qube "banking"  --uses--> vault    own home folder, green frame
 +-- qube "sketchy"  --uses--> alpine   home lives in RAM, red frame, deleted on close
```

**Templates** are complete Linux systems (Alpine or Arch) kept read-only. Programs you install into a template appear in every qube that uses it. A qube can never change its template.

**Qubes** are sandboxes built on a template. Each launch is a `bwrap` process with:

- `--unshare-all`: new user, mount, PID, IPC, UTS and network namespaces (network is added back only if you allow it)
- `--cap-drop ALL`, `--die-with-parent`, `--new-session`
- the template mounted **read-only**; `/tmp`, `/run` and `/home` are private and empty except the qube's own home folder
- a **seccomp** filter that blocks risky system calls (see [Security levels](#security-levels))
- nothing else from your computer unless you share it: folders, sound, camera, a USB drive and the clipboard are each off by default

**Each qube's files** live in `~/.local/share/miniqubes/boxes/<name>/home`. Settings are a small file at `~/.config/miniqubes/boxes/<name>.toml`. A *disposable* qube keeps its home in RAM and forgets everything when you close it.

**The coloured frame.** Every app opens inside its own tiny nested Wayland desktop (a kiosk [labwc](https://github.com/labwc/labwc)) with a coloured border and the qube's name. You always see which qube a window belongs to, and the app can't see or draw over windows from other qubes. Pop-ups (a Google sign-in window, file dialogs) stay inside the qube's frame.

**The desktop session.** MiniQubes ships an optional full desktop session: labwc, waybar, a fast launcher, 1 to 9 workspaces. Every app opens through a qube. You can also use MiniQubes on top of any existing desktop.

## Features

| | |
|---|---|
| Sandboxing | bubblewrap, per-qube home, read-only templates, seccomp levels |
| Frames | coloured per-qube frame around every window |
| Templates | Alpine and Arch; create, copy and delete your own, give sensitive qubes their own |
| Move qubes between templates | switch a qube's base system without losing its data |
| Network | none, internet-only (LAN blocked), or full |
| Disposable qubes | home in RAM, wiped on close |
| Clipboard | optional text clipboard sharing, per qube |
| Folders | share specific folders read-only or read-write |
| USB drives | give **one** qube at a time access to a plugged-in drive |
| Dead man's switch | pull a USB key and the PC logs out or shuts down |
| Export / import | take qubes with you on a USB stick, optionally encrypted |
| GUI | "Manage" window for everything, plus a desktop settings window |
| Desktop | labwc + waybar session, quick launcher, dark/light theme, keybinds |

## Install

Supported: **x86_64** Linux, Arch, Debian/Ubuntu, Fedora and openSUSE based distros. Needs Python 3.11+ (the installer pulls in everything else: bubblewrap, PySide6, foot, and for the desktop labwc, waybar and friends).

```bash
git clone https://github.com/133cx-mrkaboom/MiniQubes.git
cd MiniQubes
chmod +x install.sh
./install.sh
```

Read `install.sh` first if you want to know exactly what it does; it uses `sudo` to install packages and build the base system. Options:

```
./install.sh                 install everything (CLI, GUI, desktop session, Alpine base system)
./install.sh --no-template   skip building the Alpine base system
./install.sh --no-desktop    CLI/GUI/launcher only, no labwc session
./install.sh --dry-run       show what would happen, change nothing
./install.sh --uninstall     remove it (add --purge to also delete all qubes and base systems)
```

After install:

- **Use the full desktop:** log out, pick **MiniQubes** in your login screen's session list.
- **Or use it on your current desktop:** run `miniqubes-gui`, or find "MiniQubes" in your app menu.

Building an **Arch** template needs an Arch host with `arch-install-scripts` (the installer adds it on Arch).

## Using it

1. Open **Manage** (`miniqubes-gui`, or `Super+M` in the session).
2. Click **+ New qube**, give it a name, a type and a base system.
3. Click **+ Add program** and pick from the apps installed in its template.
4. Click a program to launch it. It opens in that qube's coloured frame.

Need more programs? **Install programs...** asks for package names and which base system to install into (any package your template's distro has, for example `vlc libreoffice`).

Per-qube settings (they save as you click):

- network: none / internet only / full
- security level
- forget everything when closed (disposable)
- coloured frame on or off
- clipboard sharing on or off
- sound (also allows the microphone) and camera
- shared folders
- base system (template)
- colour

### Keybinds (desktop session)

| Keys | Action |
|---|---|
| `Super+Space` / `Super+D` / `Alt+F2` | quick launcher (fast, not a Qt app) |
| `Super+Shift+Space` | full launcher: search apps or run a command |
| `Super+M` | Manage qubes |
| `Super+,` | desktop settings |
| `Super+V` | clipboard history (CopyQ) |
| `Super+P` | power menu |
| `Super+Q` | close window |
| `Super+Shift+Q` | kill window |
| `Super+L` | log out |
| `Super+1..9` | go to desktop 1 to 9 |
| `Super+Shift+1..9` | send window to desktop |
| `Super+Ctrl+Left/Right` | previous / next desktop |
| `Super+Ctrl+Up/Down` | add / remove a desktop |
| `Super+Arrows` | maximise, minimise, snap left/right |
| `Super+F` | fullscreen |
| `Alt+Tab` | switch window |

Everything above (desktop count, light/dark, bar, wallpaper, keybinds) can be changed in **Desktop settings**, which also opens a normal system terminal and runs system upgrades. Both ask for confirmation, because they act on the real system outside any qube.

## Templates (base systems)

A template is shared by every qube that uses it. That is efficient, but it also means **a malicious program you install into a template is present in every qube on that template.** So:

> Give sensitive qubes (password vault, banking) their **own** template, and install risky software only into templates used by disposable or low-trust qubes.

In **Manage > Tools > Templates** you can:

- create a fresh **Alpine** (small, about 100 MB) or **Arch** (bigger, runs almost anything) template under any name, for example `vault`
- make a **separate copy** of an existing template
- install programs into, update, or open a root shell in a template
- delete a template nothing uses

To switch an existing qube to another template, open its settings and pick another **Base system**. Everything saved in the qube (files, logins, settings) stays. Only the programs underneath change; apps that aren't installed in the new template won't start until you install them there.

## Security levels

Each qube has a seccomp filter. It blocks dangerous system calls with an error.

| Level | Blocks |
|---|---|
| Basic (`low`) | a few risky system features |
| Standard (`standard`, default) | more: mounting, `ptrace`, kernel module and keyring calls, raw `bpf` and similar |
| Strict (`strict`) | everything in Standard plus creating namespaces. **Some programs stop working** |
| Custom | pick your own list of system calls |

This is a **denylist**: everything not listed is allowed. It is a good extra layer, not a complete one.

## Networking

- **No network**: the qube has no network at all.
- **Internet only**: internet works, but your local network (router admin, printers, other computers, other services on your PC) is blocked. Needs `passt` and `nftables`.
- **Full**: normal host networking.

## Extras

<a name="extras"></a>

**Clipboard.** Off or on per qube. When on, text is copied both ways between that qube and the desktop. Needs `wl-clipboard` installed in the template. It is a deliberate hole in the wall, so turn it off for qubes handling secrets. It is text only.

**USB drives.** *Tools > USB drives.* Plug in a drive, allow it, and choose **one** qube that may use it. The drive appears in that qube's `~/USB`. Only one qube at a time can have it, and you can switch which one. Needs `udisks2`.

**Dead man's switch.** At login you are asked if you want one. Pick a USB drive as the key and choose *log out* (closes every qube) or *shut down*. If the key is removed, it fires. It can only be switched off while the key is plugged in, and logging out normally never triggers it. Turn the question off in Desktop settings. Note: logging out does **not** re-encrypt a normal full-disk-encrypted drive; that stays unlocked until shutdown. If that matters, choose *shut down*.

**Export / import.** *Tools > Export / import qubes.* Saves qubes (settings plus saved files, without caches) into one `.mqz` file, for example on a USB stick. You can encrypt it with a passphrase (AES-256 via `gpg`). Importing on another PC:

- never trusts the file: unsafe paths are rejected, links can't escape, special files and setuid bits are dropped
- removes folder shares and turns sound/camera off (turn them on again yourself)
- lets you rename, skip or replace a qube that already exists
- needs a template with the same name on the new PC (templates are not included)

## Command line

```bash
miniqubes create school --preset alpine         # presets: alpine, arch, disposable, custom
miniqubes list
miniqubes show school
miniqubes run school -- firefox
miniqubes delete school --yes

miniqubes template list
miniqubes template build alpine                 # or: arch
miniqubes template build arch --as vault        # build under your own name
miniqubes template clone alpine work
miniqubes template install vault keepassxc      # install packages into a template
miniqubes template update vault
miniqubes template shell vault                  # root shell inside the template
miniqubes template delete work --yes

mq-transfer export school banking -o ~/qubes.mqz --encrypt
mq-transfer import ~/qubes.mqz
```

Handy tools: `mq-quick` (fast launcher), `mq-launcher` (full launcher), `mq-settings`, `mq-usb`, `mq-deadman`, `mq-transfer`, `mq-template-manager`, `mq-logout`, `mq-ws` (workspaces).

## What it does *not* protect against

Please read this part.

- **A shared kernel.** Qubes OS uses a hypervisor; MiniQubes uses Linux namespaces and seccomp. A kernel vulnerability can break out of a qube. Keep your kernel updated (a hardened kernel such as `linux-hardened` helps).
- **Targeted, skilled attackers.** This is for ordinary threats: nosy software, trackers, malware that isn't aimed specifically at you.
- **The clipboard, shared folders and USB drives you enable.** Those are bridges between qubes. Use them knowingly.
- **A compromised template.** Everything installed into a template is trusted by every qube on it. Use separate templates for things that matter.
- **Your host.** If your real system is compromised, MiniQubes can't help.
- **Anonymity.** MiniQubes is not Tor and doesn't hide your IP.
- **Unverified claims.** Don't assume a protection exists because it sounds reasonable. Read the code; the isolation logic is in `miniqubes`.

## Repository layout

| File | What it is |
|---|---|
| `miniqubes` | the CLI: templates, qubes, the sandbox itself |
| `miniqubes-gui` | the Manage window |
| `mq-quick`, `mq-launcher` | quick launcher and full launcher |
| `mq-settings` | desktop settings (workspaces, theme, bar, keybinds, system tools) |
| `mq-usb` | USB drive manager |
| `mq-deadman` | dead man's switch |
| `mq-transfer` | export / import qubes |
| `mq-template-manager` | create, copy, delete templates |
| `mq-clipsync` | clipboard bridge that runs inside a qube |
| `mq-menu`, `mq-ws`, `mq-running`, `mq-run`, `mq-logout`, `mq-profile`, `mq-tui` | desktop session helpers |
| `miniqubes-session`, `desktop/` | the labwc session and its config (bar, theme, keybinds, autostart) |
| `mq-patch.py` | applies the newer features to an older copy of `miniqubes` / `miniqubes-gui` |
| `install.sh`, `pack.sh`, `fix-pacman.sh` | installer, packager, pacman repair helper |

## Uninstall

```bash
./install.sh --uninstall           # removes programs, session entry, menu entry
./install.sh --uninstall --purge   # also deletes all base systems and all qubes (asks first)
```

## Contributing

Bug reports and pull requests are welcome. Include your distro and version, the steps to reproduce, and any error text or log (the Manage window logs to `~/.cache/miniqubes-gui.log`; inside a qube the clipboard helper logs to `/tmp/mqclip.*/log`). Don't paste passwords, keys or personal data.

## Disclaimer

MiniQubes is provided as-is, with no guarantee that it will stop surveillance, malware or any other threat. Understand what you install, review the code, and decide for yourself whether it fits your threat model.

## Licence

[MIT](LICENSE). Do whatever you like with it, just keep the credit.

*Made for people who don't want to be watched.*
