#!/usr/bin/env python3
"""Turn manual PDFs into page images for the stick.
usage: mkpages.py <pdf-dir-or-tar> <out-console-dir>
Each <key>.pdf becomes <out>/<key>/NN.jpg, longest side 1400 px, quality 80.
Pages already done are skipped, so it can be re-run."""
import os, sys, subprocess, tarfile, tempfile, glob, shutil
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
tmp = None
if src.endswith('.tar'):
    tmp = tempfile.mkdtemp()
    with tarfile.open(src) as t:
        t.extractall(tmp, filter='data')
    src = tmp
pdfs = sorted(glob.glob(os.path.join(src, '*.pdf')))
for p in pdfs:
    key = os.path.basename(p)[:-4]
    d = os.path.join(out, key)
    if os.path.isdir(d) and os.listdir(d):
        continue
    w = d + '.part'
    shutil.rmtree(w, ignore_errors=True); os.makedirs(w)
    r = subprocess.run(['pdftoppm', '-scale-to', '1400', '-jpeg', '-jpegopt', 'quality=80', p, os.path.join(w, 'p')],
                       capture_output=True, text=True)
    files = sorted(glob.glob(os.path.join(w, 'p-*.jpg')))
    if not files:
        print('FAIL', key, r.stderr[:200]); shutil.rmtree(w); continue
    for i, f in enumerate(files, 1):
        os.rename(f, os.path.join(w, '%03d.jpg' % i))
    shutil.rmtree(d, ignore_errors=True); os.rename(w, d)
    print('ok', key, len(files))
if tmp: shutil.rmtree(tmp)
