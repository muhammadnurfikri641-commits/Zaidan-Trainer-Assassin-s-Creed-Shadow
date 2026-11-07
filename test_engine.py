import ctypes, struct, sys
from unittest.mock import MagicMock
ctypes.WinDLL = lambda *a, **k: MagicMock()
import engine, caves

class Fake(engine.Game):
    def __init__(self):
        super().__init__()
        self.mem = bytearray(0x200000); self.h = 1; self.base = 0x140000000; self.size = len(self.mem)
        self.blob = self.base + 0x2000000
        self.cave_mem = bytearray(caves.BLOB_SIZE); self.cave_mem[:len(caves.BLOB)] = caves.BLOB
    def _m(self, a, n):
        if self.base <= a < self.base + self.size: return self.mem, a - self.base
        return self.cave_mem, a - self.blob
    def read(self, a, n): m, o = self._m(a, n); return bytes(m[o:o+n])
    def write(self, a, d): m, o = self._m(a, len(d)); m[o:o+len(d)] = d
    def write_code(self, a, d): self.write(a, d)
    def regions(self): yield self.base, self.size

def put(g, off, pat, fill=0xAB, caps=None):
    toks = pat.split(); b = bytearray()
    for t in toks:
        if t == '*': b.append(fill)
        elif t.startswith('s'): b += (caps or b'\x34\x12')
        else: b.append(int(t,16))
    g.mem[off:off+len(b)] = b; return bytes(b)

g = Fake()
fails = 0
# letakkan SEMUA pola (varian pertama tiap group) di offset berbeda lalu pasang/lepas
off = 0x1000
placed = {}
for name, h in caves.HOOKS.items():
    if h['pre']: put(g, off + 0x800, h['pre'][0], caps=b'\x58\x03')
    orig = put(g, off, h['pat'], caps=b'\x34\x12'); placed[name] = (off, orig); off += 0x1000
for name in caves.HOOKS:
    g2 = g
    ok = g._install(name)
    o, orig = placed[name]; h = caves.HOOKS[name]; a = g.base + o + h['off']
    code = g.read(a, h['plen'])
    tgt = a + 5 + struct.unpack('<i', code[1:5])[0]
    ret = struct.unpack('<Q', g.read(g.blob + h['ret'], 8))[0]
    good = ok and code[0] == 0xE9 and tgt == g.blob + h['cave'] and ret == a + h['plen'] and code[5:] == b'\x90'*(h['plen']-5)
    for po, key in h['patches']:
        v = struct.unpack('<i', g.read(g.blob + h['cave'] + po, 4))[0]
        good = good and v == (0x0358 if key == 'sr1' else 0x1234)
    g._restore(name)
    good = good and g.read(a, h['plen']) == orig[h['off']:h['off']+h['plen']]
    print(('OK  ' if good else 'FAIL'), name, hex(a))
    fails += not good
# varian dmg: pola A tidak ada -> harus jatuh ke varian berikutnya lewat acquire
g.scan_cache.clear(); g.active.clear(); g.refs.clear()
print("fails:", fails)
# pola capture + wildcard
rx, caps = engine.compile_pattern("41 80 BE s1.2 00 00 00 74 * F6")
print(caps, bool(rx.search(b'\x00'+bytes.fromhex('4180BE3412000000 74FF F6'.replace(' ','')))))
