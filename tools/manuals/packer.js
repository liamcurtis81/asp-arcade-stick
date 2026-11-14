window.packTar = async function(base, list, prefix, chunkMB){
  window.pk = {done:0, total:list.length, files:[], err:[]};
  const enc = new TextEncoder();
  const hdr = (name, size) => {
    const h = new Uint8Array(512);
    const put = (s, off, len) => { const b = enc.encode(s); h.set(b.subarray(0, len), off); };
    put(name, 0, 100); put('0000644\0', 100, 8); put('0000000\0', 108, 8); put('0000000\0', 116, 8);
    put(size.toString(8).padStart(11, '0') + '\0', 124, 12);
    put(Math.floor(Date.now()/1000).toString(8).padStart(11, '0') + '\0', 136, 12);
    put('        ', 148, 8); h[156] = 48; put('ustar\0', 257, 6); put('00', 263, 2);
    let sum = 0; for (let i = 0; i < 512; i++) sum += h[i];
    put(sum.toString(8).padStart(6, '0') + '\0 ', 148, 8);
    return h;
  };
  let parts = [], bytes = 0, n = 1;
  const flush = () => {
    if (!parts.length) return;
    parts.push(new Uint8Array(1024));
    const b = new Blob(parts, {type: 'application/x-tar'});
    const a = document.createElement('a'); a.href = URL.createObjectURL(b);
    a.download = prefix + '_' + String(n).padStart(2, '0') + '.tar'; document.body.appendChild(a); a.click();
    window.pk.files.push(a.download + ' ' + b.size);
    parts = []; bytes = 0; n++;
  };
  for (const [key, file] of list) {
    try {
      const r = await fetch(base + encodeURIComponent(file));
      if (!r.ok) throw r.status;
      const d = new Uint8Array(await r.arrayBuffer());
      const name = key.replace(/[\\/:*?"<>|]/g, '_') + '.pdf';
      parts.push(hdr(name.length > 99 ? name.slice(0, 95) + '.pdf' : name, d.length), d);
      const pad = (512 - d.length % 512) % 512; if (pad) parts.push(new Uint8Array(pad));
      bytes += d.length;
      if (bytes > chunkMB * 1e6) flush();
    } catch (e) { window.pk.err.push(key + ' ' + e); }
    window.pk.done++;
  }
  flush();
  window.pk.finished = true;
};
