@echo off
chcp 65001 >nul
rem 打包成单个 exe（输出在 dist 文件夹）。首次使用先运行：python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
cd /d "%~dp0"
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "流水分析助手" --icon "%~dp0assets\icon.ico" ^
  --paths "%~dp0app" --add-data "%~dp0app\web;web" ^
  --collect-all rapidocr --hidden-import segno ^
  --exclude-module tkinter --exclude-module reportlab --exclude-module dev_server ^
  --distpath "%~dp0dist" --workpath "%~dp0build" --specpath "%~dp0build" ^
  "%~dp0app\main.py"
echo.
echo 完成：dist\流水分析助手.exe
