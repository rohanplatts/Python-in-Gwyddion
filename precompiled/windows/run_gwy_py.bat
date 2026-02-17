@echo off
set "GWYDDION_LOGFILE=%USERPROFILE%\Desktop\gwyddion.log"

set "GWY_PYTHON_EXE=C:\Users\rnpla\anaconda3\envs\dat_to_sxm\python.exe"
set "GWY_PYTHON_SCRIPT=C:\gwy-python-bridge\absurd_process.py"

REM Keep Gwyddion’s own bin first; append MSYS2 at end only if needed later.
set "PATH=C:\Program Files\Gwyddion\bin;%PATH%"

"C:\Program Files\Gwyddion\bin\gwyddion.exe" --new-instance --log-to-file
