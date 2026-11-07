@echo off
REM Butuh Python 64-bit (python.org). Hasil: dist\ZaidanTrainer\ZaidanTrainer.exe
REM Ikon Z biru + metadata publisher ZaidanStore disematkan ke exe.
py -3 -m pip install --upgrade pyinstaller pillow
py -3 -m PyInstaller --noconfirm --clean --noconsole --uac-admin --name ZaidanTrainer ^
  --icon zaidan.ico --version-file version_info.txt ^
  --add-data "zaidan.ico;." zaidan_trainer.py
echo.
echo Selesai. Buka folder dist\ZaidanTrainer\ lalu jalankan ZaidanTrainer.exe
pause
