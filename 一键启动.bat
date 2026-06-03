@echo off
title Welearn Helper
cd /d "%~dp0"
pip install -r requirement.txt
python -u main.py
pause
