from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import redis
import pika
import json
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

cache = redis.from_url(REDIS_URL, decode_responses=True)

MEDICOS = {
    "ortopedista": [
        {"id": 1, "nome": "Dr. João Silva", "foto": "joao.png", "categoria": "Ortopedista", "horarios_vagos": ["10:00", "14:00", "16:00"]},
        {"id": 2, "nome": "Dra. Maria Souza", "foto": "maria.png", "categoria": "Ortopedista", "horarios_vagos": ["09:00", "11:00", "15:00"]},
        {"id": 3, "nome": "Dr. Pedro Alves", "foto": "pedro.png", "categoria": "Ortopedista", "horarios_vagos": ["08:00", "13:00", "17:00"]}
    ],
    "pediatra": [],
    "cirurgiao": []
}

class Agendamento(BaseModel):
    paciente_nome: str
    medico_id: int
    dia: str
    horario: str

# Modelo novo apenas para os dados de cancelamento
class Cancelamento(BaseModel):
    medico_id: int
    dia: str
    horario: str

@app.get("/medicos/{categoria}")
def listar_medicos(categoria: str):
    if categoria not in MEDICOS:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    return MEDICOS[categoria]

@app.get("/horarios/{medico_id}")
def obter_horarios_vagos(medico_id: int, dia: str):
    medico_encontrado = None
    for medicos_lista in MEDICOS.values():
        for m in medicos_lista:
            if m["id"] == medico_id:
                medico_encontrado = m
                break
        if medico_encontrado:
            break
            
    if not medico_encontrado:
        raise HTTPException(status_code=404, detail="Médico não encontrado")

    horarios_disponiveis = []
    for hora in medico_encontrado["horarios_vagos"]:
        lock_key = f"lock:medico:{medico_id}:dia:{dia}:hora:{hora}"
        if not cache.exists(lock_key):
            horarios_disponiveis.append(hora)

    return horarios_disponiveis

@app.post("/agendar")
def agendar_consulta(dados: Agendamento):
    lock_key = f"lock:medico:{dados.medico_id}:dia:{dados.dia}:hora:{dados.horario}"
    
    conseguiu_travar = cache.setnx(lock_key, "reservado")
    
    if not conseguiu_travar:
        raise HTTPException(status_code=409, detail="Ops! Este horário acabou de ser reservado por outra pessoa.")
    
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue='fila_consultas', durable=True)
        
        mensagem = json.dumps(dados.model_dump())
        channel.basic_publish(
            exchange='',
            routing_key='fila_consultas',
            body=mensagem,
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
    except Exception as e:
        cache.delete(lock_key)
        raise HTTPException(status_code=500, detail="Erro interno no servidor.")

    return {
        "status": "sucesso",
        "mensagem": f"Consulta confirmada para o dia {dados.dia} às {dados.horario}!"
    }

# NOVA ROTA: Libera a vaga no Redis
@app.post("/cancelar")
def cancelar_consulta(dados: Cancelamento):
    lock_key = f"lock:medico:{dados.medico_id}:dia:{dados.dia}:hora:{dados.horario}"
    cache.delete(lock_key) # Destrava o horário no Redis
    return {"status": "sucesso", "mensagem": "Horário liberado!"}

app.mount("/", StaticFiles(directory="static", html=True), name="static")