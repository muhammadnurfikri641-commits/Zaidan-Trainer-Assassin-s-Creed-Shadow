"""Zaidan Trainer - Assassin's Creed Shadows (Windows x64).
Trainer buatan sendiri: semua mekanisme ada di engine.py + caves.asm (bisa diaudit)."""
import ctypes
import queue
import sys
import threading
import time
import tkinter as tk

import math
import struct
import os
import traceback
import webbrowser
from engine import Game, TrainerError, to_i32


def _base_dir():
    return os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))


def log_error(ctx):
    """Tulis traceback lengkap ke zaidan_error.log di folder trainer (untuk debug)."""
    try:
        with open(os.path.join(_base_dir(), "zaidan_error.log"), "a", encoding="utf-8") as fh:
            fh.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {ctx}\n{traceback.format_exc()}")
    except Exception:
        pass

APP_NAME = "ZAIDAN TRAINER"
GAME_NAME = "Assassin's Creed Shadows"

# Penyesuaian teleport ke marker: menambah ketinggian agar tidak masuk ke dalam tanah
# (di FLiNG juga "jatuh dari langit"). Aktifkan God Mode / Infinite Health agar tidak kena damage jatuh.
TP_MARKER_HEIGHT = 150.0

# ---------------- palet ----------------
BG, SIDE, CARD, CARD_H = "#0b0b10", "#101018", "#15151e", "#1b1b28"
TXT, MUTED, ACC, GOLD, OK, ERR = "#ecebf4", "#8b8aa0", "#e11d48", "#f5b83d", "#22c55e", "#ef4444"
FONT = "Segoe UI"
PUBLISHER = "ZaidanStore"
# (label, url) untuk area credit di navbar. Email memakai skema mailto:.
CREDITS = [
    ("GitHub", "https://github.com/muhammadnurfikri641-commits"),
    ("Email", "mailto:muhammadnurfikri641@gmail.com"),
    ("Instagram", "https://instagram.com/zaidanstore217a"),
]

VK_CTRL = 0x11
NUM = {str(i): 0x60 + i for i in range(10)}
NUM.update({"+": 0x6B, "-": 0x6D, ".": 0x6E})

# id, nama, hotkey(ctrl, tombol), kategori, tipe, default, deskripsi
FEATURES = [
    ("god", "God Mode / Ignore Hits", (0, "1"), "Player", "toggle", None, "Abaikan semua serangan musuh."),
    ("health", "Infinite Health", (0, "2"), "Player", "toggle", None, "Berlaku saat nilai health ter-update."),
    ("adren", "Infinite Adrenaline", (0, "3"), "Player", "toggle", None, "Berlaku saat adrenaline bertambah."),
    ("skillcd", "Skills Instant Cooldown", (0, "4"), "Player", "toggle", None, "Cooldown skill langsung nol."),
    ("oxygen", "Infinite Oxygen", (0, "7"), "Player", "toggle", None, "Napas bawah air tidak habis."),
    ("stealth", "Stealth Mode", (0, "8"), "Player", "toggle", None,
     "Musuh tak bisa melihatmu, tapi tetap melawan jika kamu menyentuh/menyerang mereka."),
    ("dmgmul", "Damage Multiplier", (0, "+"), "Combat", "value", "5", "Pengali damage ke musuh."),
    ("defmul", "Defense Multiplier", (0, "-"), "Combat", "value", "5", "Damage yang kamu terima dibagi nilai ini."),
    ("onehit", "Super Damage / One Hit Kills", (0, "."), "Combat", "toggle", None, "Sekali serang musuh langsung tumbang."),
    ("armormul", "Armor Damage Multiplier", (0, "0"), "Combat", "value", "5", "Pengali damage ke armor musuh."),
    ("superarmor", "Super Armor Damage / One Hit Break Armor", (0, "9"), "Combat", "toggle", None, "Armor musuh hancur sekali pukul."),
    ("ration", "Ration Won't Decrease", (0, "5"), "Resources", "toggle", None, "Ration tidak berkurang saat dipakai."),
    ("throw", "Throwables Won't Decrease", (0, "6"), "Resources", "toggle", None, "Throwable tidak berkurang saat dipakai."),
    ("item", "Edit Selected Item / Money Amount", (1, "1"), "Resources", "actionvalue", "99999",
     "Buka item bag, pilih item, lalu jalankan. Hanya bekerja jika jumlah item 2 atau lebih. "
     "Angka tampilan baru ter-update setelah pungut item / save-load."),
    ("exp", "Infinite Exp", (1, "2"), "Resources", "toggle", None, "Berlaku saat kamu mendapat exp."),
    ("expmul", "Exp Multiplier", (1, "3"), "Resources", "value", "5", "Pengali exp yang didapat."),
    ("mastery", "Edit Total Mastery Points", (1, "4"), "Resources", "value", "99",
     "Berlaku saat nilai mastery point ter-update. Angka tampilan = sisa poin."),
    ("speed", "Set Game Speed", (1, "0"), "World", "value", "2", "Kecepatan game (1 = normal, 0.5 = lambat)."),
    ("freeze", "Freeze Daytime", (1, "8"), "World", "toggle", None, "Waktu dalam game berhenti."),
    ("hour", "Daytime +1 Hour", (1, "9"), "World", "action", None, "Majukan waktu 1 jam."),
    ("saveloc", "Save Location", (1, "5"), "Teleport", "action", None, "Simpan posisi karakter saat ini."),
    ("tpsaved", "Teleport to Saved Location", (1, "6"), "Teleport", "action", None,
     "Jangan teleport saat berenang, memanjat, atau jatuh."),
    ("tpmark", "Teleport to Marker Location", (1, "7"), "Teleport", "action", None,
     "Pasang marker di peta dulu. Kamu akan jatuh dari ketinggian: aktifkan God Mode / Infinite Health."),
]
CATS = ["Semua", "Player", "Combat", "Resources", "World", "Teleport"]

DMG_DEPS = ("player", "godmode", "dmg")  # hook damage butuh player & godmode (penanda "yang kena = pemain")


# ---------------- logika fitur ----------------
class Logic:
    def __init__(self, game):
        self.g = game
        self.lock = threading.RLock()
        self.saved = None
        self.exp_loop = False
        self.on = {}

    def _acq(self, *groups):
        for gp in groups:
            self.g.acquire(gp)

    def _rel(self, *groups):
        for gp in reversed(groups):
            self.g.release(gp)

    def _flag(self, name, on, kind="i", val=1):
        (self.g.set_f32 if kind == "f" else self.g.set_i32)(name, val if on else 0)

    def apply(self, fid, on, val):
        g = self.g
        if not g.is_alive():
            raise TrainerError("Game belum berjalan / belum terhubung.")
        with self.lock:
            m = getattr(self, "f_" + fid)
            return m(on, val)

    # --- Player ---
    def f_god(self, on, v):
        self._acq("player", "godmode") if on else None
        self._flag("godmode", on)
        self._rel("player", "godmode") if not on else None

    def f_health(self, on, v):
        self._acq(*DMG_DEPS) if on else None
        self._flag("health", on)
        self._rel(*DMG_DEPS) if not on else None

    def f_adren(self, on, v):
        if on:
            self._acq("focus_add", "focus_sub")
        else:
            self._rel("focus_add", "focus_sub")

    def f_skillcd(self, on, v):
        self._acq("skillcd") if on else self._rel("skillcd")

    def f_oxygen(self, on, v):
        self._acq("oxygen") if on else None
        self._flag("infinite_oxygen", on)
        self._rel("oxygen") if not on else None

    def f_stealth(self, on, v):
        self.g.stealth(on)

    # --- Combat ---
    def f_dmgmul(self, on, v):
        self._acq(*DMG_DEPS) if on else None
        self._flag("dmgmul_f", on, "f", float(v))
        self._rel(*DMG_DEPS) if not on else None

    def f_defmul(self, on, v):
        self._acq(*DMG_DEPS) if on else None
        self._flag("defmul_f", on, "f", float(v))
        self._rel(*DMG_DEPS) if not on else None

    def f_onehit(self, on, v):
        self._acq(*DMG_DEPS) if on else None
        self._flag("dmg", on)
        self._rel(*DMG_DEPS) if not on else None

    def f_armormul(self, on, v):
        self._acq("armordmg") if on else None
        self._flag("armordmgmul_f", on, "f", float(v))
        self._rel("armordmg") if not on else None

    def f_superarmor(self, on, v):
        self._acq("armordmg") if on else None
        self._flag("armordmg", on)
        self._rel("armordmg") if not on else None

    # --- Resources ---
    def f_ration(self, on, v):
        self._acq("potions") if on else None
        self._flag("ration_wont_decrease", on)
        self._rel("potions") if not on else None

    def f_throw(self, on, v):
        self._acq("throwables") if on else None
        self._flag("throwables_wont_decrease", on)
        self._rel("throwables") if not on else None

    def f_item(self, on, v):
        # hook sekali-pasang (tetap terpasang sampai trainer ditutup)
        if not self.g.refs.get("selptr"):
            self._acq("selptr")
        if not self.g.refs.get("edititem"):
            self._acq("edititem")
        self.g.set_i32("selected_item", to_i32(float(v)))
        return "Nilai dikirim. Pungut item / save-load agar tampilan ter-update."

    def f_exp(self, on, v):
        if on:
            self._acq("exp")
            self.exp_loop = True
            threading.Thread(target=self._exp_worker, daemon=True).start()
        else:
            self.exp_loop = False
            time.sleep(0.3)
            self._rel("exp")

    def _exp_worker(self):  # hook mereset flag setelah tiap pemakaian -> pasang ulang selama aktif
        while self.exp_loop and self.g.is_alive():
            try:
                self.g.set_i32("exp", 1)
            except TrainerError:
                break
            time.sleep(0.15)

    def f_expmul(self, on, v):
        self._acq("exp") if on else None
        self._flag("expmul_f", on, "f", float(v))
        self._rel("exp") if not on else None

    def f_mastery(self, on, v):
        self._acq("skillpts") if on else None
        self._flag("mastery_points", on, "i", to_i32(float(v)))
        self._rel("skillpts") if not on else None

    # --- World ---
    def f_speed(self, on, v):
        if on:
            self._acq("gamespeed")
            self.g.set_f32("gamespeed_f", max(0.05, float(v)))
        else:
            self.g.set_f32("gamespeed_f", 0.0)  # sinyal reset ke kecepatan normal
            time.sleep(0.6)                      # beri waktu hook menjalankan reset
            self._rel("gamespeed")

    def f_freeze(self, on, v):
        self._acq("daytime") if on else None
        self._flag("freeze_daytime", on)
        self._rel("daytime") if not on else None

    def f_hour(self, on, v):
        if not self.g.refs.get("daytime"):
            self._acq("daytime")
        self.g.set_i32("daytime_add", 1)

    # --- Teleport ---
    def _ploc(self):
        if not self.g.refs.get("ploc"):
            self._acq("ploc")
        ptr = self.g.get_q("location")
        if not ptr:
            raise TrainerError("Posisi belum terbaca: gerakkan karakter sebentar lalu coba lagi.")
        return ptr

    def f_saveloc(self, on, v):
        self.saved = self.g.read_vec3(self._ploc())
        return "Lokasi tersimpan."

    def f_tpsaved(self, on, v):
        if not self.saved:
            raise TrainerError("Simpan lokasi dulu (Ctrl+Num 5).")
        self.g.write_vec3(self._ploc(), self.saved)

    def f_tpmark(self, on, v):
        if not self.g.refs.get("waypoint"):
            self._acq("waypoint")
        wp = self.g.read_vec3(self.g.sym("waypoint_location"))
        if not any(wp):
            raise TrainerError("Marker belum terbaca: pasang marker di peta lalu coba lagi.")
        cur = self.g.read_vec3(self._ploc())
        tgt = list(wp)
        tgt[2] = (tgt[2] if abs(tgt[2]) > 1.0 else cur[2]) + TP_MARKER_HEIGHT
        self.g.write_vec3(self._ploc(), tgt)


# ---------------- widget ----------------
class Switch(tk.Canvas):
    def __init__(self, master, command, **kw):
        super().__init__(master, width=48, height=26, bg=CARD, highlightthickness=0, cursor="hand2", **kw)
        self.command, self.state = command, False
        self.bind("<Button-1>", lambda e: self.command(not self.state))
        self.draw()

    def set(self, v):
        self.state = v
        self.draw()

    def draw(self):
        self.delete("all")
        col = ACC if self.state else "#2a2a3a"
        r = 13
        self.create_oval(1, 1, 2 * r, 2 * r, fill=col, outline=col)
        self.create_oval(48 - 2 * r, 1, 47, 2 * r, fill=col, outline=col)
        self.create_rectangle(r, 1, 48 - r, 2 * r, fill=col, outline=col)
        x = 48 - r - 1 if self.state else r + 1
        self.create_oval(x - 9, 4, x + 9, 22, fill="#ffffff", outline="#ffffff")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} - {GAME_NAME}")
        self.geometry("1000x720")
        self.minsize(860, 560)
        self.configure(bg=BG)
        self._set_icon()
        self.game = Game()
        self.logic = Logic(self.game)
        self.q = queue.Queue()
        self.cards, self.switches, self.vars = {}, {}, {}
        self.cat = "Semua"
        self.prev = {}
        self.busy = False
        self._build()
        self.after(50, self._drain)
        self.after(800, self._poll_game)
        self.after(40, self._poll_keys)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._dark_titlebar)

    # ----- UI -----
    def _credit_link(self, parent, text, url):
        lbl = tk.Label(parent, text=text, bg=BG, fg=TXT, font=(FONT, 9, "underline"), cursor="hand2")
        lbl.pack(side="left")
        lbl.bind("<Enter>", lambda e: lbl.configure(fg=ACC))
        lbl.bind("<Leave>", lambda e: lbl.configure(fg=TXT))
        # webbrowser.open aman untuk http(s) dan mailto:; gagal diam-diam tanpa menghentikan trainer
        lbl.bind("<Button-1>", lambda e: webbrowser.open(url))

    def _set_icon(self):
        """Pasang ikon Z biru (zaidan.ico). Saat dibundle PyInstaller file ada di _MEIPASS."""
        base = getattr(sys, "_MEIPASS", _base_dir())
        try:
            self.iconbitmap(os.path.join(base, "zaidan.ico"))
        except Exception:
            pass  # ikon opsional: kalau tidak ada, trainer tetap jalan

    def _dark_titlebar(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            v = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(v), 4)
        except Exception:
            pass

    def _build(self):
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", padx=22, pady=(18, 8))
        tk.Label(head, text="ZAIDAN", bg=BG, fg=TXT, font=(FONT, 24, "bold")).pack(side="left")
        tk.Label(head, text=" TRAINER", bg=BG, fg=ACC, font=(FONT, 24, "bold")).pack(side="left")
        tk.Label(head, text=f"   {GAME_NAME}", bg=BG, fg=MUTED, font=(FONT, 11)).pack(side="left", pady=(10, 0))
        self.pill = tk.Label(head, text="●  Menunggu game…", bg=CARD, fg=MUTED, font=(FONT, 10, "bold"), padx=14, pady=6)
        self.pill.pack(side="right")

        # Area credit di navbar: nama publisher + tautan GitHub / Email / Instagram
        credit = tk.Frame(head, bg=BG)
        credit.pack(side="right", padx=(0, 18), pady=(10, 0))
        tk.Label(credit, text=PUBLISHER, bg=BG, fg=GOLD, font=(FONT, 10, "bold")).pack(side="left")
        for label, url in CREDITS:
            tk.Label(credit, text="  •  ", bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left")
            self._credit_link(credit, label, url)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        side = tk.Frame(body, bg=SIDE, width=170)
        side.pack(side="left", fill="y", padx=(22, 10), pady=(0, 14))
        side.pack_propagate(False)
        self.catbtn = {}
        for c in CATS:
            b = tk.Label(side, text=c, bg=SIDE, fg=MUTED, font=(FONT, 11, "bold"), anchor="w", padx=18, pady=11, cursor="hand2")
            b.pack(fill="x")
            b.bind("<Button-1>", lambda e, c=c: self._set_cat(c))
            self.catbtn[c] = b
        tk.Frame(side, bg=SIDE).pack(fill="both", expand=True)
        off = tk.Label(side, text="Matikan semua", bg="#1d1d2a", fg=TXT, font=(FONT, 10, "bold"), pady=10, cursor="hand2")
        off.pack(fill="x", padx=14, pady=14)
        off.bind("<Button-1>", lambda e: self._all_off())

        wrap = tk.Frame(body, bg=BG)
        wrap.pack(side="left", fill="both", expand=True, padx=(0, 22), pady=(0, 14))
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))

        self.foot = tk.Label(self, text="Jalankan sebagai Administrator • hotkey Numpad aktif global", bg=SIDE, fg=MUTED,
                             font=(FONT, 10), anchor="w", padx=22, pady=8)
        self.foot.pack(fill="x", side="bottom")

        for f in FEATURES:
            self._make_card(f)
        self._set_cat("Semua")

    def _hk(self, hk):
        return ("Ctrl+" if hk[0] else "") + "Num " + hk[1]

    def _make_card(self, f):
        fid, name, hk, cat, kind, default, desc = f
        card = tk.Frame(self.inner, bg=CARD, highlightbackground="#22222f", highlightthickness=1)
        card.columnconfigure(0, weight=1)
        left = tk.Frame(card, bg=CARD)
        left.grid(row=0, column=0, sticky="ew", padx=16, pady=12)
        tk.Label(left, text=name, bg=CARD, fg=TXT, font=(FONT, 12, "bold"), anchor="w").pack(anchor="w")
        tk.Label(left, text=desc, bg=CARD, fg=MUTED, font=(FONT, 9), anchor="w", justify="left", wraplength=430).pack(anchor="w", pady=(2, 0))
        col = 1
        if default is not None:
            v = tk.StringVar(value=default)
            self.vars[fid] = v
            e = tk.Entry(card, textvariable=v, width=8, bg="#0e0e15", fg=TXT, insertbackground=TXT, relief="flat",
                         font=(FONT, 11), justify="center", highlightthickness=1, highlightbackground="#2a2a3a", highlightcolor=ACC)
            e.grid(row=0, column=col, padx=6, ipady=5)
            col += 1
        tk.Label(card, text=self._hk(hk), bg="#22190a", fg=GOLD, font=(FONT, 9, "bold"), padx=8, pady=3).grid(row=0, column=col, padx=8)
        col += 1
        if kind in ("toggle", "value"):
            sw = Switch(card, command=lambda on, fid=fid: self._request(fid, on))
            sw.grid(row=0, column=col, padx=(6, 16))
            self.switches[fid] = sw
        else:
            b = tk.Label(card, text="Jalankan", bg=ACC, fg="white", font=(FONT, 10, "bold"), padx=16, pady=6, cursor="hand2")
            b.grid(row=0, column=col, padx=(6, 16))
            b.bind("<Button-1>", lambda e, fid=fid: self._request(fid, True))
        self.cards[fid] = (card, cat)

    def _set_cat(self, c):
        self.cat = c
        for k, b in self.catbtn.items():
            b.configure(bg=ACC if k == c else SIDE, fg="white" if k == c else MUTED)
        for card, cat in self.cards.values():
            card.pack_forget()
        for f in FEATURES:
            card, cat = self.cards[f[0]]
            if c in ("Semua", cat):
                card.pack(fill="x", pady=5)
        self.canvas.yview_moveto(0)

    # ----- eksekusi fitur -----
    def _msg(self, text, ok=True):
        self.foot.configure(text=text, fg=OK if ok else ERR)

    def _request(self, fid, on):
        f = next(x for x in FEATURES if x[0] == fid)
        val = self.vars[fid].get() if fid in self.vars else None
        if f[4] in ("toggle", "value"):
            self.switches[fid].set(on)
        if val is not None:
            try:
                if not math.isfinite(float(val)):
                    raise ValueError
            except ValueError:
                self._msg("Nilai harus berupa angka wajar (tidak boleh kosong atau terlalu besar).", False)
                if fid in self.switches:
                    self.switches[fid].set(not on)
                return

        def work():
            try:
                note = self.logic.apply(fid, on, val)
                self.q.put(lambda: self._msg(f"{f[1]}: {('ON' if on else 'OFF') if f[4] in ('toggle','value') else 'OK'}"
                                             + (f" - {note}" if note else "")))
            except TrainerError as ex:
                self.q.put(lambda ex=ex: (self._msg(str(ex), False), fid in self.switches and self.switches[fid].set(not on)))
            except (OverflowError, ValueError, OSError, TypeError) as ex:  # noqa
                log_error(f"{f[1]}")
                self.q.put(lambda ex=ex: (self._msg(f"{f[1]} gagal ({type(ex).__name__}): {ex}", False),
                                          fid in self.switches and self.switches[fid].set(not on)))
            except Exception as ex:  # noqa
                log_error(f"{f[1]}")
                self.q.put(lambda ex=ex: (self._msg(f"{f[1]} gagal: {ex}", False),
                                          fid in self.switches and self.switches[fid].set(not on)))

        threading.Thread(target=work, daemon=True).start()

    def _all_off(self):
        for fid, sw in list(self.switches.items()):
            if sw.state:
                self._request(fid, False)

    def _drain(self):
        try:
            while True:
                self.q.get_nowait()()
        except queue.Empty:
            pass
        self.after(50, self._drain)

    # ----- status game & hotkey -----
    def _poll_game(self):
        g = self.game
        try:
            if g.h and not g.is_alive():
                g.detach()
                self.logic = Logic(g)
                for sw in self.switches.values():
                    sw.set(False)
            if not g.h and not self.busy:
                pid = g.find_process()
                if pid:
                    self.busy = True
                    self.pill.configure(text="●  Menghubungkan…", fg=GOLD)

                    def att():
                        try:
                            g.attach()
                            self.q.put(lambda: self._msg("Terhubung ke game."))
                        except TrainerError as ex:
                            self.q.put(lambda ex=ex: self._msg(str(ex), False))
                        self.busy = False

                    threading.Thread(target=att, daemon=True).start()
            if g.h:
                self.pill.configure(text=f"●  Terhubung (PID {g.pid})", fg=OK)
            elif not self.busy:
                self.pill.configure(text="●  Menunggu game…", fg=MUTED)
        except Exception:
            pass
        self.after(1000, self._poll_game)

    def _poll_keys(self):
        try:
            gk = ctypes.windll.user32.GetAsyncKeyState
            ctrl = bool(gk(VK_CTRL) & 0x8000)
            for f in FEATURES:
                fid, _, (need_ctrl, key), _, kind, *_ = f
                down = bool(gk(NUM[key]) & 0x8000)
                was = self.prev.get(fid, False)
                self.prev[fid] = down
                if down and not was and ctrl == bool(need_ctrl):
                    if kind in ("toggle", "value"):
                        self._request(fid, not self.switches[fid].state)
                    else:
                        self._request(fid, True)
        except Exception:
            pass
        self.after(40, self._poll_keys)

    def _close(self):
        self.logic.exp_loop = False
        try:
            self.game.detach()  # kembalikan semua byte asli game
        finally:
            self.destroy()


if __name__ == "__main__":
    if sys.platform != "win32":
        print("Trainer ini hanya untuk Windows.")
        sys.exit(1)
    if struct.calcsize("P") != 8:
        ctypes.windll.user32.MessageBoxW(
            0, "Trainer ini butuh Python 64-bit. Python yang kamu pakai 32-bit.\n"
               "Install Python 64-bit dari python.org lalu jalankan ulang.", "Zaidan Trainer", 0x10)
        sys.exit(1)
    App().mainloop()
