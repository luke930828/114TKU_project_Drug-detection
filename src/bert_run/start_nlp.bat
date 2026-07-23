@echo off
cd /d C:\114TKU_project_Durg-detection
.venv\Scripts\uvicorn src.bert_run.api:app --host 0.0.0.0 --port 8000
pause
