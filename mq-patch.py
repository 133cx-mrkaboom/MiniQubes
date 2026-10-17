#!/usr/bin/python3
"""mq-patch.py - applies small, repeatable updates to YOUR copies of `miniqubes` and `miniqubes-gui`
(so your own edits to those files are kept). Safe to run again: finished patches are skipped, the
'internet (no LAN)' feature is applied all-or-nothing, and a file is never written if it wouldn't compile.
Usage: mq-patch.py [folder]      (default: the folder this file is in)"""
import py_compile
import shutil
import sys
import tempfile
from pathlib import Path

DNS = "10.255.255.53"
MARK = "# mq:internet"

INTERNET_BLOCK = f'''    {MARK}
    net = box["network"]
    wrap = None
    if net == "internet":
        # own network namespace via pasta (user-mode networking) + a firewall that blocks the local network.
        # fails closed: if anything is missing, nothing runs.
        pasta = shutil.which("pasta")
        nft = shutil.which("nft", path=os.environ.get("PATH", "") + ":/usr/sbin:/sbin")
        if not pasta or not nft:
            die("network 'internet' needs pasta (package: passt) and nft (package: nftables); refusing to run without them")
        if "--unshare-all" in args:
            args.remove("--unshare-all")
        args = ["--unshare-user", "--unshare-ipc", "--unshare-pid", "--unshare-uts", "--unshare-cgroup-try"] + args
        (DATA / a.name).mkdir(parents=True, exist_ok=True)
        resolv = DATA / a.name / "resolv.conf"
        resolv.write_text("nameserver {DNS}\\n")
        rules = Path(rt) / f"mq-net-{{a.name}}.nft"
        rules.write_text(
            "add table inet mq\\n"
            "add chain inet mq out {{ type filter hook output priority 0; policy accept; }}\\n"
            'add rule inet mq out oifname "lo" accept\\n'
            "add rule inet mq out ip daddr {DNS} accept\\n"
            "add rule inet mq out ip daddr {{ 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16, "
            "224.0.0.0/4, 255.255.255.255 }} drop\\n")
        rules.chmod(0o644)
        args += ["--ro-bind", str(resolv), "/etc/resolv.conf"]
        script = ('"$1" -f "$2" || {{ echo "miniqubes: couldn\\'t set up the LAN firewall, refusing to run" >&2; exit 97; }}; '
                  'shift 2; exec "$@"')
        wrap = [pasta, "-4", "--config-net", "--no-map-gw", "-t", "none", "-T", "none", "-u", "none", "-U", "none",
                "--dns-forward", "{DNS}", "--", "sh", "-c", script, "sh", nft, str(rules)]
    if wrap:
        os.execvp(wrap[0], [*wrap, "bwrap", *args, *cmd])
    os.execvp("bwrap", ["bwrap", *args, *cmd])'''

EXEC_PLAIN = '    os.execvp("bwrap", ["bwrap", *args, *cmd])'
EXEC_HALF = ('    if wrap:\n        os.execvp(wrap[0], [*wrap, "bwrap", *args, *cmd])\n'
             '    os.execvp("bwrap", ["bwrap", *args, *cmd])')


def patch_net(text, say):
    problems = []
    if MARK in text:
        return text, problems
    t = text
    ok = True
    for old, new in (
        ('if n in ("none", "direct"):', 'if n in ("none", "direct", "internet"):'),
        ('die("network must be: none | direct")', 'die("network must be: none | direct | internet")'),
        ('help="none | direct")', 'help="none | direct | internet (no local network)")'),
    ):
        if old in t:
            t = t.replace(old, new)
        elif new not in t:
            ok = False
    if EXEC_HALF in t:
        t = t.replace(EXEC_HALF, INTERNET_BLOCK)
    elif t.count(EXEC_PLAIN) == 1:
        t = t.replace(EXEC_PLAIN, INTERNET_BLOCK)
    else:
        ok = False
    if ok:
        say("patched: network mode 'internet' (no local network)")
        return t, problems
    problems.append("network mode 'internet' (no local network)")
    if EXEC_HALF in text:   # repair a half-applied earlier update so the file works again
        text = text.replace(EXEC_HALF, EXEC_PLAIN)
        say("repaired a half-applied update")
    return text, problems


CLIP_MARK = "# mq:clipboard"
CLIP_OLD = '        cmd = ["labwc", "-S", shlex.join(cmd)]\n'
CLIP_NEW = f'''        {CLIP_MARK}
        # share the text clipboard with the desktop (mq-clipsync runs inside the frame); opt a qube out by
        # listing its name in ~/.config/miniqubes/clipboard.deny
        deny = Path(os.environ.get("MQ_CONF", Path.home() / ".config/miniqubes/boxes")).parent / "clipboard.deny"
        try:
            denied = a.name in deny.read_text().split()
        except OSError:
            denied = False
        if not denied and Path("/usr/local/bin/mq-clipsync").exists():
            args += ["--ro-bind", "/usr/local/bin/mq-clipsync", "/run/mq-clipsync"]
            cmd = ["/run/mq-clipsync", *cmd]
''' + CLIP_OLD


CLIP_UP_OLD = "        if not denied and Path("
CLIP_UP_NEW = '        if box.get("clipboard", True) and not denied and Path('

BOX_OLD = ("    if \"frame\" in box:\n"
           "        lines.append(f\"frame = {'true' if box['frame'] else 'false'}\")\n")
BOX_NEW = BOX_OLD + ("    if \"clipboard\" in box:\n"
                     "        lines.append(f\"clipboard = {'true' if box['clipboard'] else 'false'}\")\n")

POP_MARK = "mq:popups"
POP_EDITS = [
    # first window of a qube: maximized and fixed; every later window (popups, sign-in windows) floats
    ("        '    <windowRule identifier=\"*\"><action name=\"Maximize\"/></windowRule>\\n'\n",
     "        '    <windowRule identifier=\"*\" matchOnce=\"true\"><fixedPosition>yes</fixedPosition>"
     "<action name=\"Maximize\"/></windowRule>\\n'\n"
     "        '    <windowRule type=\"dialog\"><action name=\"ToggleAlwaysOnTop\"/></windowRule>\\n'\n"),
    ("        '  <titlebar><layout>icon:close</layout></titlebar>\\n'\n",
     "        '  <titlebar><layout>icon:close</layout></titlebar>\\n'\n"
     "        '  <placement><policy>center</policy></placement>\\n'\n"
     "        '  <focus><raiseOnFocus>no</raiseOnFocus></focus>\\n'\n"),
    # clicking inside a window no longer raises it, so the main window can't cover its own popup
    ("        '<action name=\"Focus\"/><action name=\"Raise\"/></mousebind></context>\\n'\n",
     "        '<action name=\"Focus\"/></mousebind></context>\\n'\n"),
    # popups can be dragged by the title bar and resized from the edges (the main window is fixed above)
    ("        '  </mouse>\\n'\n",
     "        '    <!-- mq:popups -->\\n'\n"
     "        '    <context name=\"Title\"><mousebind button=\"Left\" action=\"Press\"><action name=\"Focus\"/>"
     "<action name=\"Raise\"/></mousebind><mousebind button=\"Left\" action=\"Drag\"><action name=\"Move\"/>"
     "</mousebind></context>\\n'\n"
     "        '    <context name=\"Titlebar\"><mousebind button=\"Left\" action=\"Press\"><action name=\"Focus\"/>"
     "<action name=\"Raise\"/></mousebind><mousebind button=\"Left\" action=\"Drag\"><action name=\"Move\"/>"
     "</mousebind></context>\\n'\n"
     "        + ''.join(f'    <context name=\"{c}\"><mousebind button=\"Left\" action=\"Drag\"><action name=\"Resize\"/>'\n"
     "                  '</mousebind></context>\\n' for c in ('Top', 'Bottom', 'Left', 'Right', 'TLCorner', 'TRCorner', 'BLCorner', 'BRCorner'))\n"
     "        + '  </mouse>\\n'\n"),
]


CLIP_FIX = [('"/usr/local/bin/mq-clipsync", "/usr/local/bin/mq-clipsync"]', '"/usr/local/bin/mq-clipsync", "/run/mq-clipsync"]'),
            ('cmd = ["mq-clipsync", *cmd]', 'cmd = ["/run/mq-clipsync", *cmd]')]


def patch_clip(text, say):
    problems = []
    for o, n in CLIP_FIX:      # the template is read-only, so the helper must be mounted under /run (a tmpfs)
        if o in text:
            text = text.replace(o, n)
            say("fixed: clipboard helper mount point")
    if CLIP_MARK in text:
        if CLIP_UP_OLD in text and CLIP_UP_NEW not in text:
            text = text.replace(CLIP_UP_OLD, CLIP_UP_NEW, 1)
            say("patched: per-qube clipboard setting")
    elif text.count(CLIP_OLD) == 1:
        text = text.replace(CLIP_OLD, CLIP_NEW.replace("        if not denied and Path(", CLIP_UP_NEW, 1))
        say("patched: shared clipboard between qubes and the desktop")
    else:
        problems.append("shared clipboard")
    if "clipboard" not in text.split("def write_box", 1)[-1].split("\ndef ", 1)[0]:
        if text.count(BOX_OLD) == 1:
            text = text.replace(BOX_OLD, BOX_NEW)
            say("patched: qube file keeps the clipboard setting")
        else:
            problems.append("qube file clipboard setting")
    if POP_MARK not in text:
        if all(text.count(o) == 1 for o, _ in POP_EDITS):
            for o, n in POP_EDITS:
                text = text.replace(o, n)
            say("patched: popups / sign-in windows open as their own floating windows")
        else:
            problems.append("popup windows")
    return text, problems


USB_MARK = "# mq:usb"
USB_HELPER = '''# mq:usb  (USB drive for ONE qube; set up in Manage > USB drives, stored in ~/.config/miniqubes/usb.toml)
def mountpoint_of(dev):
    try:
        lines = Path("/proc/self/mountinfo").read_text().splitlines()
    except OSError:
        return None
    for ln in lines:
        left, _, right = ln.partition(" - ")
        f, r = left.split(), right.split()
        if len(r) >= 2 and r[1] == dev:
            return re.sub(r"\\\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), f[4])
    return None


def usb_mount_for(name, conf=None, bydev="/dev/disk/by-uuid"):
    """(mount point, read_only) of the USB drive given to this qube, or None. Only the ONE 'active' qube gets it."""
    try:
        cfg = tomllib.loads((conf or CONF.parent / "usb.toml").read_text())
    except (OSError, ValueError):
        return None
    for uuid, d in cfg.get("drive", {}).items():
        if d.get("active") != name or name not in d.get("allowed", []):
            continue
        dev = Path(bydev) / uuid
        if not dev.exists():
            continue                          # unplugged
        real = str(dev.resolve())
        mp = mountpoint_of(real)
        if not mp:                            # replugged: mount it again (no root needed with udisks)
            try:
                subprocess.run(["udisksctl", "mount", "-b", real], capture_output=True, timeout=30)
            except (OSError, subprocess.SubprocessError):
                pass
            mp = mountpoint_of(real)
        if mp and Path(mp).is_dir():
            return mp, bool(d.get("readonly"))
    return None


'''
USB_RUN_OLD = '    if box["network"] == "direct":\n'
USB_RUN_NEW = '''    usb = usb_mount_for(a.name)
    if usb:
        args += ["--ro-bind" if usb[1] else "--bind", usb[0], "/home/user/USB"]

''' + USB_RUN_OLD
USB_DEF_OLD = "def cmd_run(a):\n"


def patch_usb(text, say):
    if USB_MARK in text:
        return text, []
    if text.count(USB_RUN_OLD) != 1 or text.count(USB_DEF_OLD) != 1:
        return text, ["USB drive for one qube"]
    say("patched: USB drive for one qube")
    return text.replace(USB_DEF_OLD, USB_HELPER + USB_DEF_OLD).replace(USB_RUN_OLD, USB_RUN_NEW), []


def patch_cli(text, say):
    text, p1 = patch_net(text, say)
    text, p2 = patch_clip(text, say)
    text, p3 = patch_usb(text, say)
    return text, p1 + p2 + p3


HELPER_GUI = 'def in_root(root, p):\n    """Follow symlinks as if `root` were / (links inside a template point at the template, not at this computer)."""\n    root, cur, hops = Path(root), Path(root), 0\n    parts = list(Path(p).relative_to(root).parts)\n    while parts:\n        part = parts.pop(0)\n        if part == "..":\n            cur = cur.parent if cur != root else cur\n            continue\n        nxt = cur / part\n        if nxt.is_symlink() and hops < 40:\n            hops += 1\n            t = os.readlink(nxt)\n            if t.startswith("/"):\n                cur, parts = root, list(Path(t).parts[1:]) + parts\n            else:\n                parts = list(Path(t).parts) + parts\n        else:\n            cur = nxt\n    return cur\n\n\n'


GUI_EDITS = [
    ("clipboard checkbox",
     '        self.frame.toggled.connect(self.save_settings)\n',
     '        self.frame.toggled.connect(self.save_settings)\n'
     '        self.clip = QCheckBox("Share clipboard with the desktop and other qubes")\n'
     '        self.clip.setToolTip("Copy/paste text between this qube and everything else. Works for colored-frame qubes. "\n'
     '                             "Turn off for qubes that handle passwords or anything private.")\n'
     '        self.clip.toggled.connect(self.save_settings)\n'),
    ("clipboard row", '        sf.addRow(self.frame)\n', '        sf.addRow(self.frame)\n        sf.addRow(self.clip)\n'),
    ("clipboard hint",
     '        sf.addRow(self.clip)\n',
     '        sf.addRow(self.clip)\n'
     '        sf.addRow(QLabel("Needs wl-clipboard in the base system: Install programs... and add  wl-clipboard"))\n'),
    ("install hint",
     '"For sound, include: libpulse\\nIdeas: "',
     '"For sound, include: libpulse\\nFor copy/paste between qubes, include: wl-clipboard\\nIdeas: "'),
    ("settings button",
     '        lv.addWidget(bg)\n',
     '        lv.addWidget(bg)\n'
     '        sett = QPushButton("Desktop settings...")\n'
     '        sett.setToolTip("Number of desktops, light/dark, bar, wallpaper, keybinds, system terminal and upgrades")\n'
     '        sett.clicked.connect(lambda: subprocess.Popen(["mq-settings"], start_new_session=True))\n'
     '        lv.addWidget(sett)\n'),
    ("template links helper",
     'def template_apps(root):\n',
     HELPER_GUI + 'def template_apps(root):\n'),
    ("template links read",
     '            cp.read(f, encoding="utf-8")\n',
     '            cp.read(in_root(root, f), encoding="utf-8")\n'),
    ("template links icon",
     '    return QIcon(best) if best else QIcon()\n',
     '    return QIcon(str(in_root(root, best))) if best else QIcon()\n'),
    ("usb button",
     '        lv.addWidget(sett)\n',
     '        lv.addWidget(sett)\n'
     '        usbb = QPushButton("USB drives...")\n'
     '        usbb.setToolTip("Give one qube at a time access to a plugged-in USB drive")\n'
     '        usbb.clicked.connect(lambda: subprocess.Popen(["mq-usb"], start_new_session=True))\n'
     '        lv.addWidget(usbb)\n'),
    ("clipboard load",
     '            self.frame.setChecked(bool(b.get("frame", True)))\n',
     '            self.frame.setChecked(bool(b.get("frame", True)))\n'
     '            self.clip.setChecked(bool(b.get("clipboard", True)))\n'),
    ("clipboard save",
     '        b["frame"] = self.frame.isChecked()\n',
     '        b["frame"] = self.frame.isChecked()\n        b["clipboard"] = self.clip.isChecked()\n'),
    ("network choice widget",
     '        self.internet = QCheckBox("Internet access")\n        self.internet.toggled.connect(self.save_settings)\n',
     '        self.internet = QComboBox()\n'
     '        self.internet.addItem("No network", "none")\n'
     '        self.internet.addItem("Internet only (blocks your local network)", "internet")\n'
     '        self.internet.addItem("Full (internet + your local network)", "direct")\n'
     '        self.internet.currentIndexChanged.connect(self.save_settings)\n'),
    ("network row label", '        sf.addRow(self.internet)\n', '        sf.addRow("Network", self.internet)\n'),
    ("network load",
     '            self.internet.setChecked(b.get("network") == "direct")\n',
     '            i = self.internet.findData(b.get("network", "none"))\n'
     '            self.internet.setCurrentIndex(i if i >= 0 else 0)\n'),
    ("network save",
     '        b["network"] = "direct" if self.internet.isChecked() else "none"\n',
     '        b["network"] = self.internet.currentData()\n'),
    ("qube kind label",
     'return "Everyday" if b.get("network") == "direct" else "Offline"',
     'return "Everyday" if b.get("network") in ("direct", "internet") else "Offline"'),
]


def patch_gui(text, say):
    problems = []
    for name, old, new in GUI_EDITS:
        if new in text:
            continue
        if text.count(old) == 1:
            text = text.replace(old, new)
            say(f"patched: {name}")
        else:
            problems.append(name)
    return text, problems


def run_one(path, fn):
    if not path.exists():
        print(f"  {path.name}: not found, skipped")
        return 0
    say = lambda m: print(f"  {path.name}: {m}")
    orig = path.read_text()
    new, problems = fn(orig, say)
    if problems and path.name == "miniqubes-gui":
        new = orig        # GUI changes are all-or-nothing too
    if new != orig:
        with tempfile.TemporaryDirectory() as d:     # never write a file that doesn't compile
            tmp = Path(d) / path.name
            tmp.write_text(new)
            try:
                py_compile.compile(str(tmp), doraise=True, cfile=str(Path(d) / "x.pyc"))
            except py_compile.PyCompileError as e:
                print(f"  {path.name}: update would break the file, NOT applied: {e.msg}")
                return 1
        shutil.copy2(path, str(path) + ".bak-before-patch")
        path.write_text(new)
    for p in problems:
        print(f"  {path.name}: could not apply: {p} (your copy differs; attach the file and tell Claude)")
    return len(problems)


def main():
    here = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    bad = run_one(here / "miniqubes", patch_cli) + run_one(here / "miniqubes-gui", patch_gui)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
