FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system trialguard \
    && adduser --system --ingroup trialguard --home /home/trialguard trialguard \
    && mkdir -p /data \
    && chown -R trialguard:trialguard /data /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY dashboard ./dashboard
COPY synthetic_data ./synthetic_data
COPY pytest.ini ./

# Bundle synthetic demo data only. Persistent user/study state lives in /data.
RUN python synthetic_data/generate.py

USER trialguard

EXPOSE 8000 8501

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
