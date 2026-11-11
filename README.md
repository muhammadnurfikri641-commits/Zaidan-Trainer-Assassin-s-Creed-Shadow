# Zaidan Trainer - Assassin's Creed Shadows

Trainer buatan sendiri (Python + tkinter). Tanpa Malware segala jenis, tanpa DLL, tanpa koneksi internet.

## Cara pakai
1. Install Python 64-bit, lalu jalankan `build.bat` (atau langsung `py zaidan_trainer.py` sebagai Administrator).
2. Jalankan game, lalu buka ZaidanTrainer.exe (Run as Administrator). NumLock harus ON.
3. Aktifkan fitur lewat switch atau hotkey Numpad (Num = tanpa Ctrl, Ctrl+Num = tahan Ctrl).

## Isi
- `zaidan_trainer.py` UI dark + logika 23 fitur + hotkey
- `engine.py`        attach, AOB scan, pasang/lepas hook (semua WinAPI terlihat jelas)
- `caves.asm`        source assembly seluruh code cave (bisa diaudit)
- `caves.py`         hasil rakitan caves.asm (dibuat oleh tools/gen_caves.py)
- `tools/`           generator + tes simulasi (Linux, opsional)

## Catatan
- Pola AOB mengikuti game v1.0 - v1.1.8. Jika game sudah update dan pola tak ditemukan, fitur itu menampilkan error (tidak crash).
- Menutup trainer mengembalikan semua byte asli game.
- Pakai hanya untuk mode single-player/offline.
