FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# A flag -u é obrigatória aqui para forçar o Python a mostrar 
# os prints imediatamente no terminal do Docker Compose
CMD ["python", "-u", "main.py"]