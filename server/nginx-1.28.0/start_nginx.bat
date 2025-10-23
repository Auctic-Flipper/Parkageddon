@echo off
cd /d C:\nginx-1.28.0

echo Starting nginx...
nginx.exe

if %errorlevel% neq 0 (
    echo Failed to start nginx. Error code: %errorlevel%
) else (
    echo Nginx started successfully.
)

pause

