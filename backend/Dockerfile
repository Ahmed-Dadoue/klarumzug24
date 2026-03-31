FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./requirements.txt

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app ./app
COPY main.py ./main.py
COPY api.py ./api.py
COPY legacy ./legacy
COPY umzug_preis_model.pkl ./umzug_preis_model.pkl
COPY umzug_daten.csv ./umzug_daten.csv

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
