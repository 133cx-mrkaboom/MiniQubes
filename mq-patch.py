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


def patch_cli(text, say):
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


GUI_EDITS = [
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
