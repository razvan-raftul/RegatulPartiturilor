@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python nu este instalat. Se deschide pagina de descarcare. Instaleaza Python 3.13 si bifeaza Add Python to PATH, apoi porneste din nou.
  start https://www.python.org/downloads/windows/
  pause
  exit /b
)
if not exist ".instalat" (
  echo Prima pornire: se instaleaza componentele, dureaza cateva minute.
  py -3 -m pip install --upgrade -r cerinte.txt
  if errorlevel 1 (
    echo Instalarea nu a reusit. Verifica internetul si porneste din nou.
    pause
    exit /b
  )
  echo gata> ".instalat"
)
start "" pyw -3 "Regatul Partiturilor.pyw" %1
