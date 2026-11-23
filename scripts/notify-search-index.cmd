@echo off
pushd "%~dp0.."
"backend\.venv\Scripts\python.exe" "scripts\notify-search-index.py" %*
set "index_result=%errorlevel%"
popd
if not "%index_result%"=="0" pause
exit /b %index_result%
