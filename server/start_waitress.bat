@echo off
cd /d C:\Users\Wireless\Documents\GitHub\Parkageddon\server
call venv\Scripts\activate.bat
waitress-serve --listen=127.0.0.1:8000 --call "app:create_app"
