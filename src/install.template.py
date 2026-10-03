#!/usr/bin/env python3
"""Install / update / remove the Mainsail pre-print checks (nozzle size, Z-offset
reminder, filament-changed, hardened-nozzle for CF/GF) on a Mainsail instance.

  install.py                          # this machine, Mainsail folder auto-detected
  install.py --dir /var/www/mainsail  # other web root
  install.py --host pi@printer.local [--dir /home/pi/mainsail]   # over ssh
  install.py --remove                 # restore the original index.html / sw.js

Safe to re-run: it replaces the previous copy of the script, and the script's
filename carries a content hash so browsers always fetch the new one.
Re-run it after a Mainsail update (updates overwrite index.html and sw.js).
"""
import argparse, glob, hashlib, os, re, shutil, subprocess, sys

JS = r'''@@JS@@'''

TAG = '<script src="/%s" defer></script>'
TAG_RE = re.compile(r'<script src="/nozzle-check[^"]*\.js" defer></script>')
SW_RE = re.compile(r'(url:"index\.html",revision:")[0-9a-f]+(")')


def write_atomic(path, data, like):
    tmp = os.path.join(os.path.dirname(path), '.' + os.path.basename(path) + '.tmp')
    with open(tmp, 'w') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    st = os.stat(like)
    try:
        os.chown(tmp, st.st_uid, st.st_gid)
    except PermissionError:
        pass
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def set_sw_revision(d, index_html):
    sw = os.path.join(d, 'sw.js')
    if not os.path.exists(sw):
        print('note: no sw.js, skipping service-worker revision')
        return
    s = open(sw).read()
    rev = hashlib.md5(index_html.encode()).hexdigest()
    s2, n = SW_RE.subn(lambda m: m.group(1) + rev + m.group(2), s)
    if n == 0:
        print('WARNING: index.html entry not found in sw.js; browsers may need a service-worker reset')
        return
    write_atomic(sw, s2, sw)


def install(d):
    index = os.path.join(d, 'index.html')
    if not os.path.exists(index):
        sys.exit('no index.html in %s - is that a Mainsail directory?' % d)
    html = open(index).read()
    if '</head>' not in html:
        sys.exit('index.html has no </head>; unexpected layout')
    name = 'nozzle-check-%s.js' % hashlib.md5(JS.encode()).hexdigest()[:8]
    for suffix in ('index.html', 'sw.js'):
        bak = os.path.join(d, suffix + '.pre-nozzle-check')
        if not os.path.exists(bak) and os.path.exists(os.path.join(d, suffix)):
            if suffix == 'index.html' and TAG_RE.search(html):
                continue  # already patched; don't back up a patched copy
            shutil.copy2(os.path.join(d, suffix), bak)
    write_atomic(os.path.join(d, name), JS, index)
    html = TAG_RE.sub('', html)
    html = html.replace('</head>', TAG % name + '</head>', 1)
    write_atomic(index, html, index)
    set_sw_revision(d, html)
    for old in glob.glob(os.path.join(d, 'nozzle-check*.js')):
        if os.path.basename(old) != name:
            os.remove(old)
    os.sync()
    print('installed %s into %s' % (name, d))
    print('Hard-refresh Mainsail (Ctrl+Shift+R), possibly twice, to pick it up.')


def remove(d):
    index = os.path.join(d, 'index.html')
    html = TAG_RE.sub('', open(index).read())
    write_atomic(index, html, index)
    set_sw_revision(d, html)
    for old in glob.glob(os.path.join(d, 'nozzle-check*.js')):
        os.remove(old)
    os.sync()
    print('removed from %s (index.html now has the script tag stripped)' % d)


def find_dir():
    cands = [os.path.expanduser('~/mainsail'), '/home/pi/mainsail', '/var/www/mainsail']
    cands += sorted(glob.glob('/home/*/mainsail'))
    for f in glob.glob('/etc/nginx/sites-enabled/*') + glob.glob('/etc/nginx/conf.d/*.conf'):
        try:
            cands += re.findall(r'^\s*root\s+(/[^;\s$]+);', open(f).read(), re.M)
        except OSError:
            pass
    for c in cands:
        if os.path.exists(os.path.join(c, 'index.html')) and os.path.exists(os.path.join(c, 'sw.js')):
            return c
    sys.exit('could not find a Mainsail folder; pass --dir /path/to/mainsail')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', help='Mainsail web root (default: auto-detect)')
    ap.add_argument('--host', help='user@host to run this on over ssh')
    ap.add_argument('--remove', action='store_true')
    a = ap.parse_args()
    if a.host:
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=15', a.host, 'python3', '-']
        cmd += (['--dir', a.dir] if a.dir else []) + (['--remove'] if a.remove else [])
        sys.exit(subprocess.run(cmd, stdin=open(os.path.abspath(__file__))).returncode)
    d = os.path.abspath(a.dir) if a.dir else find_dir()
    if not os.access(d, os.W_OK):
        sys.exit('no write access to %s - re-run as the owning user or with sudo' % d)
    (remove if a.remove else install)(d)


if __name__ == '__main__':
    main()
