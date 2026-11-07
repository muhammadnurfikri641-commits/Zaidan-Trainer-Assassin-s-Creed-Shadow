"""Engine memori Zaidan Trainer (Windows x64, Python 64-bit).
Mekanisme: attach ke proses game -> scan AOB di modul utama -> pasang `jmp` ke code cave
(milik kita sendiri, hasil rakitan caves.asm) -> flag/nilai ditulis ke data page bersama.
Tidak ada DLL injection, tidak ada koneksi jaringan, tidak ada file lain yang dijalankan.
"""
import ctypes as C
import ctypes.wintypes as W
import re
import struct
import time

import caves

PROCESS_NAMES = ("ACShadows.exe", "ACShadows_Plus.exe")

# --- konstanta WinAPI ---
PROCESS_ALL = 0x1F0FFF
MEM_COMMIT, MEM_RESERVE, MEM_RELEASE = 0x1000, 0x2000, 0x8000
PAGE_RWX = 0x40
EXEC_FLAGS = (0x10, 0x20, 0x40, 0x80)
TH32_PROC, TH32_THREAD, TH32_MOD, TH32_MOD32 = 0x2, 0x4, 0x8, 0x10
THREAD_SUSPEND = 0x2

k32 = C.WinDLL("kernel32", use_last_error=True)
P = C.c_void_p
k32.OpenProcess.restype, k32.OpenProcess.argtypes = P, [W.DWORD, W.BOOL, W.DWORD]
k32.CloseHandle.argtypes = [P]
k32.ReadProcessMemory.argtypes = [P, P, P, C.c_size_t, C.POINTER(C.c_size_t)]
k32.WriteProcessMemory.argtypes = [P, P, P, C.c_size_t, C.POINTER(C.c_size_t)]
k32.VirtualAllocEx.restype, k32.VirtualAllocEx.argtypes = P, [P, P, C.c_size_t, W.DWORD, W.DWORD]
k32.VirtualFreeEx.argtypes = [P, P, C.c_size_t, W.DWORD]
k32.VirtualProtectEx.argtypes = [P, P, C.c_size_t, W.DWORD, C.POINTER(W.DWORD)]
k32.VirtualQueryEx.restype = C.c_size_t
k32.FlushInstructionCache.argtypes = [P, P, C.c_size_t]
k32.CreateToolhelp32Snapshot.restype = P
k32.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]
k32.OpenThread.restype, k32.OpenThread.argtypes = P, [W.DWORD, W.BOOL, W.DWORD]
k32.WaitForSingleObject.argtypes = [P, W.DWORD]
for _fn in ("Process32FirstW", "Process32NextW", "Module32FirstW", "Module32NextW", "Thread32First", "Thread32Next"):
    getattr(k32, _fn).argtypes = [P, P]
k32.SuspendThread.argtypes = [P]
k32.ResumeThread.argtypes = [P]


class MBI(C.Structure):
    _fields_ = [("BaseAddress", P), ("AllocationBase", P), ("AllocationProtect", W.DWORD), ("PartitionId", W.WORD),
                ("RegionSize", C.c_size_t), ("State", W.DWORD), ("Protect", W.DWORD), ("Type", W.DWORD)]


k32.VirtualQueryEx.argtypes = [P, P, C.POINTER(MBI), C.c_size_t]  # tanpa ini alamat 64-bit meluap (argumen ke-2)


class PROCENTRY(C.Structure):
    _fields_ = [("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ProcessID", W.DWORD), ("th32DefaultHeapID", C.c_size_t),
                ("th32ModuleID", W.DWORD), ("cntThreads", W.DWORD), ("th32ParentProcessID", W.DWORD),
                ("pcPriClassBase", C.c_long), ("dwFlags", W.DWORD), ("szExeFile", C.c_wchar * 260)]


class MODENTRY(C.Structure):
    _fields_ = [("dwSize", W.DWORD), ("th32ModuleID", W.DWORD), ("th32ProcessID", W.DWORD), ("GlblcntUsage", W.DWORD),
                ("ProccntUsage", W.DWORD), ("modBaseAddr", P), ("modBaseSize", W.DWORD), ("hModule", P),
                ("szModule", C.c_wchar * 256), ("szExePath", C.c_wchar * 260)]


class THREADENTRY(C.Structure):
    _fields_ = [("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ThreadID", W.DWORD), ("th32OwnerProcessID", W.DWORD),
                ("tpBasePri", C.c_long), ("tpDeltaPri", C.c_long), ("dwFlags", W.DWORD)]


class TrainerError(Exception):
    pass


USER_MIN, USER_MAX = 0x10000, 0x7FFFFFFFFFFF  # rentang alamat user-mode Windows x64


def chk_ptr(a):
    """Pastikan alamat valid sebelum dikirim ke WinAPI (mencegah OverflowError di ctypes)."""
    if not isinstance(a, int) or not (USER_MIN <= a <= USER_MAX):
        raise TrainerError("Alamat memori tidak valid (%r). Posisi/pointer belum siap, coba ulangi aksi." % (a,))
    return a


def to_i32(v):
    """Batasi angka ke rentang int32 agar tidak meluap saat ditulis ke memori game."""
    n = int(v)  # ValueError/OverflowError ditangani pemanggil
    return max(-2**31, min(2**31 - 1, n))


def compile_pattern(pat):
    """'48 8B * s1.2' -> (regex, [nama capture]). '*' = 1 byte bebas, 's1.2' = capture 2 byte."""
    parts, caps = [], []
    for t in pat.split():
        if t == "*":
            parts.append(b".")
        elif t.startswith("s"):
            caps.append(t.split(".")[0])
            parts.append(b"(..)")
        else:
            parts.append(re.escape(bytes([int(t, 16)])))
    return re.compile(b"".join(parts), re.DOTALL), caps


class Game:
    def __init__(self):
        self.h = None
        self.pid = 0
        self.base = 0
        self.size = 0
        self.blob = 0          # alamat blob cave di proses game
        self.active = {}       # nama hook varian -> dict(addr, orig, plen)
        self.refs = {}         # group -> jumlah fitur yang memakai
        self.group_variant = {}
        self.scan_cache = {}
        self.stealth_addr = None

    # ---------- attach ----------
    def find_process(self):
        snap = k32.CreateToolhelp32Snapshot(TH32_PROC, 0)
        pe = PROCENTRY()
        pe.dwSize = C.sizeof(pe)
        found = 0
        ok = k32.Process32FirstW(snap, C.byref(pe))
        while ok:
            if pe.szExeFile.lower() in [n.lower() for n in PROCESS_NAMES]:
                found = pe.th32ProcessID
                break
            ok = k32.Process32NextW(snap, C.byref(pe))
        k32.CloseHandle(snap)
        return found

    def is_alive(self):
        return bool(self.h) and k32.WaitForSingleObject(self.h, 0) == 0x102  # WAIT_TIMEOUT

    def attach(self):
        pid = self.find_process()
        if not pid:
            raise TrainerError("Game belum berjalan.")
        h = k32.OpenProcess(PROCESS_ALL, False, pid)
        if not h:
            raise TrainerError("Gagal membuka proses game. Jalankan trainer sebagai Administrator.")
        snap = k32.CreateToolhelp32Snapshot(TH32_MOD | TH32_MOD32, pid)
        me = MODENTRY()
        me.dwSize = C.sizeof(me)
        if not k32.Module32FirstW(snap, C.byref(me)):
            k32.CloseHandle(snap)
            raise TrainerError("Gagal membaca modul game.")
        self.base, self.size = me.modBaseAddr or 0, me.modBaseSize
        k32.CloseHandle(snap)
        self.h, self.pid = h, pid
        self._alloc_blob()
        return pid

    def detach(self):
        try:
            for name in list(self.active):
                self._restore(name)
        except Exception:
            pass
        if self.h:
            k32.CloseHandle(self.h)
        self.__init__()

    # ---------- memori ----------
    def read(self, addr, n):
        chk_ptr(addr)
        buf = (C.c_ubyte * n)()
        got = C.c_size_t()
        if not k32.ReadProcessMemory(self.h, addr, buf, n, C.byref(got)) or got.value != n:
            raise TrainerError("Gagal membaca memori @%X" % addr)
        return bytes(buf)

    def write(self, addr, data):
        chk_ptr(addr)
        got = C.c_size_t()
        if not k32.WriteProcessMemory(self.h, addr, data, len(data), C.byref(got)):
            raise TrainerError("Gagal menulis memori @%X (coba jalankan sebagai Administrator)" % addr)

    def write_code(self, addr, data):
        """Tulis ke halaman kode (ubah proteksi sementara, thread game di-suspend sebentar)."""
        chk_ptr(addr)
        threads = self._suspend_threads()
        try:
            old = W.DWORD()
            k32.VirtualProtectEx(self.h, addr, len(data), PAGE_RWX, C.byref(old))
            self.write(addr, data)
            k32.VirtualProtectEx(self.h, addr, len(data), old.value, C.byref(old))
            k32.FlushInstructionCache(self.h, addr, len(data))
        finally:
            self._resume_threads(threads)

    def _suspend_threads(self):
        out = []
        snap = k32.CreateToolhelp32Snapshot(TH32_THREAD, 0)
        te = THREADENTRY()
        te.dwSize = C.sizeof(te)
        ok = k32.Thread32First(snap, C.byref(te))
        while ok:
            if te.th32OwnerProcessID == self.pid:
                th = k32.OpenThread(THREAD_SUSPEND, False, te.th32ThreadID)
                if th:
                    k32.SuspendThread(th)
                    out.append(th)
            ok = k32.Thread32Next(snap, C.byref(te))
        k32.CloseHandle(snap)
        return out

    def _resume_threads(self, ths):
        for th in ths:
            k32.ResumeThread(th)
            k32.CloseHandle(th)

    # ---------- alokasi blob dekat modul (agar jmp rel32 cukup) ----------
    def _alloc_blob(self):
        size = caves.BLOB_SIZE
        end = self.base + self.size
        cand = []
        a = self.base - 0x10000
        while a > 0x10000 and self.base - a < 0x70000000:
            cand.append(a)
            a -= 0x100000
        a = (end + 0xFFFF) & ~0xFFFF
        while a - end < 0x70000000:
            cand.append(a)
            a += 0x100000
        for a in cand:
            p = k32.VirtualAllocEx(self.h, a & ~0xFFFF, size, MEM_COMMIT | MEM_RESERVE, PAGE_RWX)
            if p:
                if abs(p - self.base) > 0x7FF00000 or abs(p + size - end) > 0x7FF00000:
                    k32.VirtualFreeEx(self.h, p, 0, MEM_RELEASE)
                    continue
                self.blob = p
                self.write(p, caves.BLOB.ljust(size, b"\0"))
                return
        raise TrainerError("Tidak menemukan ruang memori di dekat modul game untuk code cave.")

    def sym(self, name):
        return self.blob + caves.DATA[name]

    def set_i32(self, name, v):
        self.write(self.sym(name), struct.pack("<i", to_i32(v)))

    def set_f32(self, name, v):
        f = max(-3.4e38, min(3.4e38, float(v)))  # batas float32, cegah OverflowError
        self.write(self.sym(name), struct.pack("<f", f))

    def get_q(self, name):
        return struct.unpack("<Q", self.read(self.sym(name), 8))[0]

    # ---------- AOB scan ----------
    def regions(self):
        mbi = MBI()
        a, end = self.base, self.base + self.size
        while a < end:
            if not k32.VirtualQueryEx(self.h, a, C.byref(mbi), C.sizeof(mbi)):
                break
            rs = mbi.RegionSize
            if mbi.State == MEM_COMMIT and mbi.Protect in EXEC_FLAGS:
                yield mbi.BaseAddress, rs
            a = (mbi.BaseAddress or 0) + rs

    def scan(self, pat):
        """Cari pola di region executable modul utama. Return (alamat, {capture}) atau None."""
        if pat in self.scan_cache:
            return self.scan_cache[pat]
        rx, caps = compile_pattern(pat)
        plen = len(pat.split())
        CH = 16 * 1024 * 1024
        res = None
        for base, rs in self.regions():
            off = 0
            while off < rs and not res:
                n = min(CH + plen, rs - off)
                try:
                    data = self.read(base + off, n)
                except TrainerError:
                    off += CH
                    continue
                m = rx.search(data)
                if m:
                    cv = {c: int.from_bytes(m.group(i + 1), "little") for i, c in enumerate(caps)}
                    res = (base + off + m.start(), cv)
                off += CH
            if res:
                break
        self.scan_cache[pat] = res
        return res

    # ---------- hook ----------
    def _install(self, name):
        h = caves.HOOKS[name]
        r = self.scan(h["pat"])
        if not r:
            return False
        addr, cap = r[0] + h["off"], dict(r[1])
        if h["pre"]:
            pr = self.scan(h["pre"][0])
            if not pr:
                return False
            cap[h["pre"][1]] = pr[1][h["pre"][1]]
        cave = self.blob + h["cave"]
        if abs(cave - (addr + 5)) > 0x7FFFFFFF:
            raise TrainerError("Code cave terlalu jauh dari target hook.")
        for off, key in h["patches"]:       # tempel offset struct hasil capture ke cave
            self.write(cave + off, struct.pack("<i", cap[key]))
        self.write(self.blob + h["ret"], struct.pack("<Q", addr + h["plen"]))
        orig = self.read(addr, h["plen"])
        patch = b"\xE9" + struct.pack("<i", cave - (addr + 5)) + b"\x90" * (h["plen"] - 5)
        self.write_code(addr, patch)
        self.active[name] = dict(addr=addr, orig=orig)
        return True

    def _restore(self, name):
        a = self.active.pop(name, None)
        if a:
            self.write_code(a["addr"], a["orig"])

    def acquire(self, group):
        """Pasang hook untuk group (coba tiap varian pola sampai ada yang cocok)."""
        if self.refs.get(group):
            self.refs[group] += 1
            return
        for name, h in caves.HOOKS.items():
            if h["group"] == group and self._install(name):
                self.refs[group] = 1
                self.group_variant[group] = name
                return
        raise TrainerError("Pola '%s' tidak ditemukan - versi game kemungkinan tidak didukung." % group)

    def release(self, group, keep=False):
        if not self.refs.get(group):
            return
        self.refs[group] -= 1
        if self.refs[group] <= 0 and not keep:
            self.refs.pop(group)
            self._restore(self.group_variant.pop(group, ""))
        elif self.refs[group] <= 0:
            self.refs[group] = 1  # dibiarkan terpasang (hook aksi sekali pakai)

    # ---------- stealth (patch langsung tanpa cave) ----------
    def stealth(self, on):
        if self.stealth_addr is None:
            r = self.scan("0F 85 * * 00 00 * 02 00 00 00 * 80 * * * 00 0F 84 * * 00 00")
            if not r:
                raise TrainerError("Pola 'stealth' tidak ditemukan - versi game kemungkinan tidak didukung.")
            self.stealth_addr = r[0] + 0x11
        self.write_code(self.stealth_addr, b"\x90\xE9" if on else b"\x0F\x84")

    # ---------- teleport ----------
    def read_vec3(self, ptr):
        chk_ptr(ptr)
        return struct.unpack("<3f", self.read(ptr, 12))

    def write_vec3(self, ptr, v):
        chk_ptr(ptr)
        self.write(ptr, struct.pack("<3f", *v))
