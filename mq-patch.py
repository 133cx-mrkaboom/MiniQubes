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


TPL_MARK = "# mq:templates"
TPL_FUNCS = '# mq:templates  (own templates: build alpine/arch under a name, clone, delete)\ndef user_conf():\n    # under sudo the boxes folder is the invoking user\'s, not root\'s\n    u = os.environ.get("SUDO_USER")\n    if os.geteuid() == 0 and u and "MQ_CONF" not in os.environ:\n        import pwd\n        return Path(pwd.getpwnam(u).pw_dir) / ".config/miniqubes/boxes"\n    return CONF\n\n\ndef boxes_using(template):\n    out = []\n    for p in sorted(user_conf().glob("*.toml")):\n        try:\n            if tomllib.loads(p.read_text()).get("template") == template:\n                out.append(p.stem)\n        except (OSError, ValueError):\n            pass\n    return out\n\n\ndef cmd_tclone(a):\n    need_root()\n    if not NAME_RE.match(a.new):\n        die("template name: lowercase letters, digits, - and _ (max 32)")\n    src, dest = TEMPLATES / a.name, TEMPLATES / a.new\n    if not src.is_dir():\n        die(f"no template \'{a.name}\'")\n    if dest.exists():\n        die(f"template \'{a.new}\' already exists")\n    print(f"copying {a.name} -> {a.new} (this can take a minute) ...")\n    try:\n        subprocess.run(["cp", "-a", "--reflink=auto", str(src), str(dest)], check=True)\n    except BaseException:\n        shutil.rmtree(dest, ignore_errors=True)\n        raise\n    print(f"template \'{a.new}\' ready. It is separate from \'{a.name}\': programs installed in one are not in the other.")\n\n\ndef cmd_tdelete(a):\n    need_root()\n    root = TEMPLATES / a.name\n    if not root.is_dir():\n        die(f"no template \'{a.name}\'")\n    users = boxes_using(a.name)\n    if users:\n        die(f"template \'{a.name}\' is used by: {\', \'.join(users)}. Move those qubes to another template first.")\n    if not a.yes and input(f"delete template \'{a.name}\'? type its name to confirm: ") != a.name:\n        die("cancelled")\n    shutil.rmtree(root)\n    print(f"deleted template \'{a.name}\'")\n\n\n'
TPL_EDITS = [('"pacstrap", "-K", str(dest), "base", "firefox", "mesa", "ttf-dejavu"]', '"pacstrap", "-K", str(dest), "base", "firefox", "mesa", "ttf-dejavu", "labwc", "foot", "wl-clipboard", "libpulse"]'), ('ca-certificates libpulse "', 'ca-certificates libpulse labwc foot wl-clipboard "'), ('    dest = TEMPLATES / a.name\n    if dest.exists():\n        die(f"template \'{a.name}\' already exists (delete {dest} to rebuild)")\n', '    name = a.as_name or a.name\n    if not NAME_RE.match(name):\n        die("template name: lowercase letters, digits, - and _ (max 32)")\n    dest = TEMPLATES / name\n    if dest.exists():\n        die(f"template \'{name}\' already exists (delete {dest} to rebuild)")\n'), ('    print(f"template \'{a.name}\' ready")\n', '    print(f"template \'{dest.name}\' ready")\n'), ('s = ts.add_parser("build"); s.add_argument("name", choices=["alpine", "arch"]); s.set_defaults(fn=cmd_tbuild)', 's = ts.add_parser("build"); s.add_argument("name", choices=["alpine", "arch"])\n    s.add_argument("--as", dest="as_name", metavar="NAME", help="save it under this template name (default: alpine / arch)")\n    s.set_defaults(fn=cmd_tbuild)'), ('    s = ts.add_parser("shell"); s.add_argument("name"); s.set_defaults(fn=cmd_tshell)\n', '    s = ts.add_parser("shell"); s.add_argument("name"); s.set_defaults(fn=cmd_tshell)\n    s = ts.add_parser("clone", help="copy a template under a new name"); s.add_argument("name"); s.add_argument("new"); s.set_defaults(fn=cmd_tclone)\n    s = ts.add_parser("delete", help="delete a template nothing uses"); s.add_argument("name"); s.add_argument("--yes", action="store_true"); s.set_defaults(fn=cmd_tdelete)\n')]
TPL_ANCHOR = "# ---------------------------------------------------------------- cli\n"


def patch_tpl(text, say):
    if TPL_MARK in text:
        return text, []
    if text.count(TPL_ANCHOR) != 1 or any(text.count(o) != 1 for o, _ in TPL_EDITS):
        return text, ["own templates (arch build / clone / delete)"]
    for o, n in TPL_EDITS:
        text = text.replace(o, n)
    say("patched: own templates (build under a name, clone, delete; arch gets labwc/foot)")
    return text.replace(TPL_ANCHOR, TPL_FUNCS + TPL_ANCHOR), []


def patch_cli(text, say):
    text, p1 = patch_net(text, say)
    text, p2 = patch_clip(text, say)
    text, p3 = patch_usb(text, say)
    text, p4 = patch_tpl(text, say)
    return text, p1 + p2 + p3 + p4


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
    ('template row',
     '        sf.addRow(self.frame)\n',
     '        self.tpl = QComboBox()\n        self.tpl.setToolTip("The base system this qube runs on. Give a sensitive qube (a password vault) its OWN base "\n                            "system (Templates...) so a program installed for another qube can never be part of it.")\n        self.tpl.activated.connect(self.move_template)\n        sf.addRow("Base system", self.tpl)\n        sf.addRow(self.frame)\n'),
    ('template load',
     '            self.fill_programs(b)\n',
     '            self.tpl.clear()\n            names = sorted(p.name for p in MQ.TEMPLATES.iterdir() if p.is_dir()) if MQ.TEMPLATES.is_dir() else []\n            cur_t = b.get("template", DEFAULT_TEMPLATE)\n            if cur_t not in names:\n                names.append(cur_t)\n            for n_t in names:\n                self.tpl.addItem(n_t, n_t)\n            self.tpl.setCurrentIndex(self.tpl.findData(cur_t))\n            self.fill_programs(b)\n'),
    ('template save',
     '        b["clipboard"] = self.clip.isChecked()\n',
     '        b["clipboard"] = self.clip.isChecked()\n        if self.tpl.currentData():\n            b["template"] = self.tpl.currentData()\n'),
    ('template helper',
     '    def build_base(self):\n',
     '    def cur_tpl(self):\n        b = self.load(self.name) if getattr(self, "name", None) else None\n        return (b or {}).get("template") or DEFAULT_TEMPLATE\n\n    def build_base(self):\n'),
    ('template update',
     'self.terminal([CLI, "template", "update", DEFAULT_TEMPLATE])',
     'self.terminal([CLI, "template", "update", self.cur_tpl()])'),
    ('template shell',
     'self.terminal([CLI, "template", "shell", DEFAULT_TEMPLATE])',
     'self.terminal([CLI, "template", "shell", self.cur_tpl()])'),
    ('template install',
     'self.terminal([CLI, "template", "install", DEFAULT_TEMPLATE, *text.split()])',
     'self.terminal([CLI, "template", "install", self.cur_tpl(), *text.split()])'),
    ('template ready',
     '        ready = (MQ.TEMPLATES / DEFAULT_TEMPLATE).is_dir()\n',
     '        ready = (MQ.TEMPLATES / self.cur_tpl()).is_dir()\n'),
    ('template label',
     'f"Base system \'{DEFAULT_TEMPLATE}\' is ready. Programs installed here appear in every qube."',
     'f"Base system \'{self.cur_tpl()}\' is ready. Programs installed here appear in every qube that uses it."'),
    ('tools buttons',
     '        lv.addWidget(usbb)\n',
     '        lv.addWidget(usbb)\n        for text_b, tip_b, prog_b in (\n                ("Templates...", "Make separate base systems (Alpine / Arch / copies), for example one just for a vault", "mq-template-manager"),\n                ("Export / import qubes...", "Take qubes with you on a USB stick, or bring them in", "mq-transfer"),\n                ("Dead man\'s switch...", "Lock or shut down when a USB key is pulled out", "mq-deadman")):\n            tb = QPushButton(text_b)\n            tb.setToolTip(tip_b)\n            tb.clicked.connect(lambda _=False, prog_b=prog_b: subprocess.Popen([prog_b], start_new_session=True))\n            lv.addWidget(tb)\n'),
    ('template upgrade',
     '        self.tpl.currentIndexChanged.connect(self.save_settings)\n',
     '        self.tpl.activated.connect(self.move_template)\n'),
    ('template move',
     '    def cur_tpl(self):\n',
     '    def running_in(self, name):\n        for d in os.scandir("/proc"):\n            if d.name.isdigit():\n                try:\n                    if Path(d.path, "comm").read_text().strip() != "bwrap":\n                        continue\n                    argv = Path(d.path, "cmdline").read_bytes().split(b"\\0")\n                except OSError:\n                    continue\n                if b"--setenv" in argv and any(argv[i] == b"MQ_BOX" and argv[i + 1].decode() == name\n                                               for i in range(len(argv) - 1)):\n                    return True\n        return False\n\n    def move_template(self, *_):\n        if self.loading or not self.name:\n            return\n        new_t = self.tpl.currentData()\n        b = self.load(self.name)\n        if b is None or not new_t or new_t == b.get("template"):\n            return\n        old_t = b.get("template")\n        back = lambda: self.tpl.setCurrentIndex(self.tpl.findData(old_t))\n        if self.running_in(self.name):\n            QMessageBox.warning(self, "Move", "Close this qube\'s programs first.")\n            back()\n            return\n        extra = ""\n        root = MQ.TEMPLATES / new_t\n        if root.is_dir() and b.get("apps"):\n            have = {shlex.join(cmd) for _n, cmd, _i in template_apps(root)}\n            gone = [a for a in b["apps"] if a not in have]\n            if gone:\n                extra = f"\\n\\n{len(gone)} of its {len(b[\'apps\'])} listed programs are not installed in \'{new_t}\' yet " \\\n                        "and won\'t start until you install them there."\n        elif not root.is_dir():\n            extra = f"\\n\\nThe base system \'{new_t}\' isn\'t set up yet."\n        if QMessageBox.question(self, "Move to another base system",\n                                f"Move \'{self.name}\' from base system \'{old_t}\' to \'{new_t}\'?\\n\\n"\n                                "Everything saved in the qube (files, logins, settings) stays exactly as it is. "\n                                "Only the programs underneath change." + extra,\n                                QMessageBox.Yes | QMessageBox.Cancel) != QMessageBox.Yes:\n            back()\n            return\n        b["template"] = new_t\n        MQ.write_box(self.name, b)\n        self.refresh()\n\n    def cur_tpl(self):\n'),
    ('new qube template combo',
     '            self.kind.addItem(f"{title}: {about}", key)\n',
     '            self.kind.addItem(f"{title}: {about}", key)\n        self.tpl = QComboBox()\n        self.tpl.addItem("Default for this type", None)\n        for t_n in sorted(p.name for p in MQ.TEMPLATES.iterdir() if p.is_dir()) if MQ.TEMPLATES.is_dir() else []:\n            self.tpl.addItem(t_n, t_n)\n        self.tpl.setToolTip("Which base system it runs on. Pick a separate one for anything sensitive (Templates... makes them).")\n'),
    ('new qube template row',
     '        form.addRow("Type", self.kind)\n',
     '        form.addRow("Type", self.kind)\n        form.addRow("Base system", self.tpl)\n'),
    ('new qube template use',
     '[CLI, "create", name, "--preset", dlg.kind.currentData()],',
     '[CLI, "create", name, "--preset", dlg.kind.currentData(),\n                            *(["--template", dlg.tpl.currentData()] if dlg.tpl.currentData() else [])],'),
    ('template install choose',
     'self.terminal([CLI, "template", "install", self.cur_tpl(), *text.split()])',
     'names = sorted(p.name for p in MQ.TEMPLATES.iterdir() if p.is_dir()) if MQ.TEMPLATES.is_dir() else []\n            if not names:\n                QMessageBox.information(self, "Install programs", "No base system exists yet. Set one up first.")\n                return\n            cur_i = names.index(self.cur_tpl()) if self.cur_tpl() in names else 0\n            tpl, ok2 = QInputDialog.getItem(self, "Install programs", "Install into which base system?\\n"\n                                            "(Only qubes that use it will see the programs.)", names, cur_i, False)\n            if ok2:\n                self.terminal([CLI, "template", "install", tpl, *text.split()])'),
    ('ui window size',
     '        self.resize(1100, 720)\n',
     '        scr = QApplication.primaryScreen().availableGeometry()\n        self.resize(min(1100, int(scr.width() * 0.92)), min(720, int(scr.height() * 0.9)))\n        self.setMinimumSize(560, 380)\n'),
    ('ui left scroll',
     '        cl.addWidget(left)\n',
     '        ls = QScrollArea()                    # the left column scrolls instead of forcing a tall window\n        ls.setWidgetResizable(True)\n        ls.setWidget(left)\n        ls.setFrameShape(QScrollArea.Shape.NoFrame)\n        ls.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)\n        ls.setMinimumWidth(250)\n        ls.setMaximumWidth(320)\n        self.qubes.setMinimumHeight(140)\n        cl.addWidget(ls)\n'),
    ('ui polish',
     '        self.reaper = QTimer(self)\n',
     '        # ---- tidy-up: one Tools menu instead of a column of buttons, wrapping text, narrow-window friendly\n        from PySide6.QtWidgets import QMenu\n        tools_menu = QMenu(self)\n        for btn in left.findChildren(QPushButton):\n            if btn.text() in ("Desktop settings...", "USB drives...", "Templates...", "Export / import qubes...",\n                              "Dead man\'s switch..."):\n                act = tools_menu.addAction(btn.text().rstrip("."))\n                act.setToolTip(btn.toolTip())\n                act.triggered.connect(lambda _=False, b=btn: b.click())\n                btn.hide()\n        tools_btn = QPushButton("Tools  \\u25be")\n        tools_btn.setMenu(tools_menu)\n        lv.addWidget(tools_btn)\n        for lab in right.findChildren(QLabel):\n            lab.setWordWrap(True)\n        for cb in (self.internet, self.security, self.tpl):\n            cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)\n            cb.setMinimumContentsLength(16)\n        sf.setRowWrapPolicy(QFormLayout.WrapLongRows)\n        self.relayout = QTimer(self)\n        self.relayout.setSingleShot(True)\n        self.relayout.timeout.connect(self.relayout_programs)\n\n        self.reaper = QTimer(self)\n'),
    ('ui methods',
     '    def fill_programs(self, b):\n',
     '    def start_tool(self, prog):\n        try:\n            subprocess.Popen([prog], start_new_session=True)\n        except OSError:\n            QMessageBox.warning(self, "Not installed", f"{prog} isn\'t installed. Run ./install.sh again from the MiniQubes folder.")\n\n    def grid_cols(self):\n        return max(1, min(6, (self.width() - 340) // 175))\n\n    def relayout_programs(self):\n        b = self.load(self.name) if self.name else None\n        if b is not None:\n            self.fill_programs(b)\n\n    def resizeEvent(self, e):\n        super().resizeEvent(e)\n        if hasattr(self, "relayout") and getattr(self, "_cols", None) != self.grid_cols():\n            self.relayout.start(120)\n\n    def fill_programs(self, b):\n'),
    ('ui grid cols',
     '        for i, (cmd, name, icon) in enumerate(progs):\n',
     '        cols = self._cols = self.grid_cols()\n        for i, (cmd, name, icon) in enumerate(progs):\n'),
    ('ui grid place',
     '            self.grid.addWidget(btn, i // 4, i % 4)\n',
     '            self.grid.addWidget(btn, i // cols, i % cols)\n'),
    ('ui tool settings',
     'subprocess.Popen(["mq-settings"], start_new_session=True)',
     'self.start_tool("mq-settings")'),
    ('ui tool usb',
     'subprocess.Popen(["mq-usb"], start_new_session=True)',
     'self.start_tool("mq-usb")'),
    ('ui tool others',
     'subprocess.Popen([prog_b], start_new_session=True)',
     'self.start_tool(prog_b)'),
    ('ui safe load',
     '        try:\n            return MQ.load_box(name)\n        except SystemExit:\n            return None\n',
     '        try:\n            b = MQ.load_box(name)\n        except (SystemExit, Exception):     # a damaged file must not take the window down\n            return None\n        for k, v in (("template", "alpine"), ("tier", "trusted"), ("color", "#888888"), ("network", "none"),\n                     ("persistent", True), ("shares", []), ("apps", [])):\n            b.setdefault(k, v)\n        return b\n'),
    ('ui font and errors',
     '    app.setStyleSheet("QWidget { font-size: 13pt; } QPushButton { padding: 8px 16px; }")\n',
     '    pt = 13 if app.primaryScreen().availableGeometry().height() >= 900 else 11\n    app.setStyleSheet(f"QWidget {{ font-size: {pt}pt; }} QPushButton {{ padding: {pt - 5}px 14px; }}")\n\n    def on_error(kind, value, tb):          # a bug in one button shouldn\'t close the window\n        import traceback\n        try:\n            log = Path.home() / ".cache" / "miniqubes-gui.log"\n            log.parent.mkdir(parents=True, exist_ok=True)\n            with open(log, "a") as f:\n                f.write("".join(traceback.format_exception(kind, value, tb)) + "\\n")\n            QMessageBox.warning(None, "Something went wrong", f"{value}\\n\\nThe window keeps running. Details: {log}")\n        except Exception:\n            pass\n    sys.excepthook = on_error\n'),
    ('ui clear layout',
     '        if w:\n            w.deleteLater()\n',
     '        if w:\n            w.hide()                 # gone at once, not "later" (no ghost buttons while resizing)\n            w.setParent(None)\n            w.deleteLater()\n'),
    ('ui group title',
     'QGroupBox("Base system (admin: changes every qube)")',
     'QGroupBox("Base system (admin)")'),
]

SKIP_IF = {"template row": "self.tpl = QComboBox()", "template install": "Install into which base system?",
           "settings button": 'self.start_tool("mq-settings")', "usb button": 'self.start_tool("mq-usb")',
           "tools buttons": "self.start_tool(prog_b)"}


def patch_gui(text, say):
    problems = []
    for name, old, new in GUI_EDITS:
        if new in text or SKIP_IF.get(name, "\0") in text:
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
