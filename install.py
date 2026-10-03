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

JS = r'''/* Nozzle diameter check for Mainsail's "Start print" dialog.
 * - Adds a "Current nozzle" box to the dialog (value kept in Moonraker DB, namespace nozzle_check).
 * - If the file was sliced for a different nozzle, Print shows a warning with Cancel / Print anyway.
 * Hooks the dialog's Vue instance (startPrint), so it needs no change to Mainsail's own bundle. */
(function () {
  var DB = '/server/database/item';
  var NS = 'nozzle_check', KEY = 'diameter';
  var current = null; // number | null, last known saved value
  var loaded = false;

  function fmt(n) { return String(Math.round(n * 1000) / 1000); }

  function loadCurrent() {
    return fetch(DB + '?namespace=' + NS + '&key=' + KEY)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        var v = j && j.result && j.result.value;
        current = typeof v === 'number' && v > 0 ? v : null;
        loaded = true;
      })
      .catch(function () { loaded = true; });
  }

  var lastType = null, lastFile = null;
  function loadLast() {
    return fetch('/server/history/list?limit=1&order=desc')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        var job = j && j.result && j.result.jobs && j.result.jobs[0];
        var t = job && job.metadata && job.metadata.filament_type;
        lastType = typeof t === 'string' && t ? t : null;
        lastFile = job ? job.filename : null;
      })
      .catch(function () {});
  }
  function sameType(a, b) { return String(a).trim().toUpperCase() === String(b).trim().toUpperCase(); }

  function saveCurrent(v) {
    current = v;
    return fetch(DB, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ namespace: NS, key: KEY, value: v })
    }).catch(function () {});
  }

  function findVm(el) {
    var vm = el && el.__vue__;
    while (vm) {
      if (typeof vm.startPrint === 'function' && vm.file) return vm;
      vm = vm.$parent;
    }
    return null;
  }

  // carbon / glass fibre filled filaments wear brass nozzles: "PA12-CF", "PETG CF", "PA-GF30", "carbon fibre" ...
  var ABRASIVE = /(?:^|[^a-z])(?:cf|gf)(?:\d|[^a-z]|$)|[a-z0-9](?:cf|gf)(?:\d*$|[^a-z])|(?:carbon|glass)[ _-]?fi/i;
  function abrasiveName(file) {
    if (!file) return null;
    var parts = [file.filament_name, file.filament_type];
    for (var i = 0; i < parts.length; i++)
      if (typeof parts[i] === 'string' && ABRASIVE.test(parts[i])) return parts[i];
    return null;
  }
  var HARDENED = 'Use a hardened nozzle for CF and GF (carbon / glass fibre) filaments - they wear a brass nozzle quickly.';

  function fileMeta(vm) {
    var n = vm.file && vm.file.nozzle_diameter, t = vm.file && vm.file.filament_type;
    var out = { n: typeof n === 'number' && n > 0 ? n : null, t: typeof t === 'string' && t ? t : null, a: abrasiveName(vm.file) };
    if (out.n !== null && out.t !== null && typeof vm.file.filament_name === 'string') return Promise.resolve(out);
    // metadata may not have arrived yet: ask Moonraker directly
    var path = ((vm.currentPath || '') + '/' + vm.file.filename).replace(/^\/+/, '');
    return fetch('/server/files/metadata?filename=' + encodeURIComponent('gcodes/' + path))
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        var m = (j && j.result) || {};
        if (out.n === null && typeof m.nozzle_diameter === 'number' && m.nozzle_diameter > 0) out.n = m.nozzle_diameter;
        if (out.t === null && typeof m.filament_type === 'string' && m.filament_type) out.t = m.filament_type;
        if (out.a === null) out.a = abrasiveName(m);
        return out;
      })
      .catch(function () { return out; });
  }

  function differs(a, b) { return Math.abs(a - b) > 0.001; }

  function warn(card, msgs, title, okLabel, cancelLabel) {
    return new Promise(function (resolve) {
      var cs = getComputedStyle(card);
      var ov = document.createElement('div');
      ov.style.cssText = 'position:fixed;inset:0;z-index:99999;display:flex;align-items:center;' +
        'justify-content:center;background:rgba(0,0,0,.6)';
      var box = document.createElement('div');
      box.style.cssText = 'max-width:400px;width:calc(100% - 32px);padding:20px 24px;border-radius:4px;' +
        'border-top:4px solid #ff9800;font-family:'+cs.fontFamily+';line-height:1.5;box-shadow:0 8px 30px rgba(0,0,0,.5);' +
        'background:' + cs.backgroundColor + ';color:' + cs.color;
      box.innerHTML = '<div style="font-size:1.25rem;font-weight:500;margin-bottom:12px"></div>' +
        '<div style="margin-bottom:20px"></div>' +
        '<div style="display:flex;justify-content:flex-end;gap:8px"></div>';
      box.children[0].textContent = title;
      msgs.forEach(function (m, k) {
        var p = document.createElement('div');
        p.textContent = m;
        if (k) p.style.marginTop = '8px';
        box.children[1].appendChild(p);
      });
      function btn(label, color, val) {
        var b = document.createElement('button');
        b.type = 'button';
        b.textContent = label;
        b.style.cssText = 'background:none;border:0;cursor:pointer;font-weight:500;' +
          'text-transform:uppercase;letter-spacing:.0892857143em;font-size:.875rem;font-family:'+cs.fontFamily+';padding:8px 12px;color:' + color;
        b.onclick = function () { ov.remove(); resolve(val); };
        box.children[2].appendChild(b);
        return b;
      }
      var cancel = btn(cancelLabel, 'inherit', false);
      btn(okLabel, '#ff5252', true);
      ov.appendChild(box);
      document.body.appendChild(ov);
      cancel.focus();
    });
  }

  function attach(content) {
    var vm = findVm(content);
    if (!vm || content.__nozzleDone) return;
    var card = content.querySelector('.v-card');
    if (!card) return;
    content.__nozzleDone = true;

    // --- input row ---
    var row = document.createElement('div');
    row.className = 'px-4';
    row.style.cssText = 'padding:12px 16px 4px;font-size:.875rem;font-family:' + getComputedStyle(card).fontFamily;
    row.innerHTML = '<label style="display:flex;align-items:center;gap:8px">Current nozzle diameter ' +
      '<input type="number" step="0.1" min="0" style="width:5em;padding:4px 6px;border:1px solid currentColor;' +
      'border-radius:4px;background:transparent;color:inherit;font-family:inherit;font-size:inherit"> mm</label>' +
      '<div class="nz-info" style="margin-top:6px;font-size:.75rem;opacity:.85"></div>' +
      '<div class="nz-abr" style="margin-top:6px;font-size:.75rem;font-weight:500;color:#ff9800"></div>' +
      '<div style="margin-top:6px;font-size:.75rem;font-weight:500;color:#ff9800">Reminder: check the Z-offset height before printing</div>';
    var input = row.querySelector('input'), info = row.querySelector('.nz-info'), abr = row.querySelector('.nz-abr');
    var text = card.querySelector('.v-card__text');
    if (text && text.nextSibling) card.insertBefore(row, text.nextSibling); else card.appendChild(row);

    var fileN = null;
    function refresh() {
      if (document.activeElement !== input && loaded) input.value = current === null ? '' : fmt(current);
      var ab = abrasiveName(vm.file);
      abr.textContent = ab ? 'This file is ' + ab + '. ' + HARDENED : '';
      var n = vm.file && vm.file.nozzle_diameter;
      fileN = typeof n === 'number' && n > 0 ? n : fileN;
      if (fileN === null) { info.textContent = ''; }
      if (fileN === null) return;
      var bad = current === null || differs(fileN, current);
      info.textContent = 'This file was sliced for a ' + fmt(fileN) + ' mm nozzle' +
        (bad ? (current === null ? ' - enter your current nozzle' : ' - does not match') : '');
      info.style.color = bad ? '#ff9800' : '';
      info.style.fontWeight = bad ? '500' : '';
      var ft = vm.file && vm.file.filament_type;
      if (lastType && typeof ft === 'string' && ft && !sameType(ft, lastType)) {
        info.textContent += '. Last print used ' + lastType + ', this file is ' + ft;
        info.style.color = '#ff9800';
        info.style.fontWeight = '500';
      }
    }
    input.addEventListener('change', function () {
      var v = parseFloat(input.value);
      saveCurrent(v > 0 ? v : null).then(refresh);
      if (!(v > 0)) input.value = '';
      refresh();
    });
    loadCurrent().then(refresh);
    loadLast().then(refresh);
    var timer = setInterval(function () {
      if (!document.body.contains(content)) { clearInterval(timer); return; }
      refresh();
    }, 500);

    // --- hook startPrint ---
    if (vm.__nozzleHooked) return;
    vm.__nozzleHooked = true;
    var orig = vm.startPrint;
    vm.startPrint = function () {
      var args = arguments, self = this;
      return Promise.all([loaded ? null : loadCurrent(), loadLast(), fileMeta(vm)]).then(function (res) {
        var f = res[2], msgs = [];
        if (f.n !== null && (current === null || differs(f.n, current)))
          msgs.push(current === null
            ? 'You have not entered the current nozzle diameter, and this file was sliced for a ' + fmt(f.n) + ' mm nozzle.'
            : 'This file was sliced for a ' + fmt(f.n) + ' mm nozzle, but the current nozzle is set to ' + fmt(current) + ' mm.');
        if (f.a !== null) msgs.push('This file uses ' + f.a + '. ' + HARDENED);
        var askFilament = f.t !== null && lastType !== null && !sameType(f.t, lastType);
        function filamentStep() {
          if (!askFilament) return orig.apply(self, args);
          return warn(card, ['The last print job (' + lastFile + ') used ' + lastType + ', but this file is ' + f.t + '.'],
            'Have you definitely changed filament?', "Yes, I've changed it", 'No, cancel')
            .then(function (go) { if (go) orig.apply(self, args); });
        }
        if (!msgs.length) return filamentStep();
        var sizeBad = f.n !== null && (current === null || differs(f.n, current));
        return warn(card, msgs, sizeBad ? 'Nozzle check' : 'Hardened nozzle needed?', sizeBad ? 'Print anyway' : 'Hardened nozzle fitted', 'Cancel')
          .then(function (go) { if (go) filamentStep(); });
      });
    };
  }

  function scan() {
    var list = document.querySelectorAll('.v-dialog__content');
    for (var i = 0; i < list.length; i++) attach(list[i]);
  }

  var pending = false;
  new MutationObserver(function () {
    if (pending) return;
    pending = true;
    requestAnimationFrame(function () { pending = false; scan(); });
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
'''

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
