@echo off
cd /d "C:\Users\윤석민\OneDrive - (주)니어스랩\바탕 화면\Claude\youtube"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo [%date% %time%] 일일 파이프라인 시작 >> logs\daily_run.log 2>&1
C:\Python314\python.exe -X utf8 main_macro.py --phase 1-6 --pick 1 --langs ko --formats longform,shorts >> logs\daily_run.log 2>&1
echo [%date% %time%] 완료 >> logs\daily_run.log 2>&1
