FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da API
COPY main.py .

# Copia a pasta estática (onde está o index.html e as imagens) para dentro do contêiner
COPY static/ ./static/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]