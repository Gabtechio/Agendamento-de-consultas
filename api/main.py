from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis
import pika
import json
import os

app = FastAPI()

# Permite que o seu HTML (Frontend) consiga fazer requisições para esta API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conexões pegando as variáveis de ambiente do Docker
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

# Conectando ao Redis
cache = redis.from_url(REDIS_URL, decode_responses=True)

# Nossos dados em memória (Regra de negócio dos médicos)
MEDICOS = {
    "ortopedista": [
        {"id": 1, "nome": "Dr. João Silva", "foto": "joao.png", "categoria": "Ortopedista", "horarios_vagos": ["10:00", "14:00", "16:00"]},
        {"id": 2, "nome": "Dra. Maria Souza", "foto": "maria.png", "categoria": "Ortopedista", "horarios_vagos": ["09:00", "11:00", "15:00"]},
        {"id": 3, "nome": "Dr. Pedro Alves", "foto": "pedro.png", "categoria": "Ortopedista", "horarios_vagos": ["08:00", "13:00", "17:00"]}
    ],
    "pediatra": [
        # Adicione os 3 pediatras aqui depois
    ],
    "cirurgiao": [
        # Adicione os 3 cirurgiões aqui depois
    ]
}

# Modelo de dados que o Frontend vai enviar
class Agendamento(BaseModel):
    paciente_nome: str
    medico_id: int
    dia: str
    horario: str

@app.get("/medicos/{categoria}")
def listar_medicos(categoria: str):
    """Retorna os médicos de uma categoria específica"""
    if categoria not in MEDICOS:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    return MEDICOS[categoria]

@app.post("/agendar")
def agendar_consulta(dados: Agendamento):
    """Recebe o pedido de agendamento e processa a concorrência"""
    
    # 1. A MÁGICA DA CONCORRÊNCIA (REDIS)
    # Criamos uma chave única para aquele horário específico daquele médico
    lock_key = f"lock:medico:{dados.medico_id}:dia:{dados.dia}:hora:{dados.horario}"
    
    # O comando SETNX (Set if Not eXists) é atômico. 
    # Retorna True se a chave foi criada. Retorna False se a chave já existia.
    conseguiu_travar = cache.setnx(lock_key, "reservado")
    
    if not conseguiu_travar:
        # Se duas pessoas clicarem juntas, a segunda cai aqui na mesma hora!
        raise HTTPException(status_code=409, detail="Ops! Este horário acabou de ser reservado por outra pessoa.")
    
    # 2. A MÁGICA DA MENSAGERIA (RABBITMQ)
    try:
        # Conecta no RabbitMQ
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        
        # Garante que a fila existe
        channel.queue_declare(queue='fila_consultas', durable=True)
        
        # Transforma os dados em JSON e envia para a fila
        mensagem = json.dumps(dados.dict())
        channel.basic_publish(
            exchange='',
            routing_key='fila_consultas',
            body=mensagem,
            properties=pika.BasicProperties(delivery_mode=2) # Torna a mensagem persistente
        )
        connection.close()
        
    except Exception as e:
        # Se o RabbitMQ estiver fora do ar, destravamos o Redis para o paciente tentar de novo
        cache.delete(lock_key)
        raise HTTPException(status_code=500, detail="Erro interno no servidor. Tente novamente.")

    # 3. Resposta imediata para o Frontend
    return {
        "status": "sucesso",
        "mensagem": f"Consulta confirmada para o dia {dados.dia} às {dados.horario}!"
    }