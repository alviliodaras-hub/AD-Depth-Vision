#!/bin/bash
cd "$(dirname "$0")"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install --default-timeout=1000 -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
