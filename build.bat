@echo off
.venv\Scripts\python -m PyInstaller --noconfirm --onefile --windowed --name naverblogbot --collect-all imageio_ffmpeg run.py
