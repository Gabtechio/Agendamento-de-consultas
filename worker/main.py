import pika
import json
import os
import time

# Pega a URL do RabbitMQ que configuramos no docker-compose
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq-broker:5672/")
ARQUIVO_JSON = "agendamentos.json"

print("⏳ Iniciando Worker... Aguardando RabbitMQ ficar pronto...", flush=True)
# Uma pequena pausa inicial para garantir que o contêiner do RabbitMQ ligou 100%
time.sleep(10) 

def salvar_no_json(dados_agendamento):
    """Função para salvar o agendamento no nosso 'banco de dados' em arquivo"""
    # Se o arquivo não existir, cria uma lista vazia
    if not os.path.exists(ARQUIVO_JSON):
        with open(ARQUIVO_JSON, 'w') as f:
            json.dump([], f)
    
    # Lê os dados atuais do arquivo
    with open(ARQUIVO_JSON, 'r') as f:
        try:
            agendamentos = json.load(f)
        except json.JSONDecodeError:
            agendamentos = []
        
    # Adiciona a nova consulta
    agendamentos.append(dados_agendamento)
    
    # Salva o arquivo atualizado
    with open(ARQUIVO_JSON, 'w') as f:
        json.dump(agendamentos, f, indent=4)
        
    print(f"💾 Salvo no JSON: {dados_agendamento['paciente_nome']} para o dia {dados_agendamento['dia']} às {dados_agendamento['horario']}")

def callback(ch, method, properties, body):
    """Função engatilhada toda vez que uma mensagem chega na fila"""
    mensagem = json.loads(body.decode('utf-8'))
    print(f"📥 [MENSAGEM RECEBIDA] RabbitMQ entregou: {mensagem}", flush=True)
    
    # Salva no arquivo JSON
    salvar_no_json(mensagem)
    
    # Simula o envio de e-mail/notificação
    print(f"📧 E-mail de confirmação enviado para o paciente {mensagem['paciente_nome']}.", flush=True)
    print("-" * 50, flush=True)
    
    # Confirma para o RabbitMQ que a mensagem foi processada e pode ser apagada da fila (ACK)
    ch.basic_ack(delivery_tag=method.delivery_tag)

try:
    # Conexão com o RabbitMQ
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    # Garante que a fila existe
    channel.queue_declare(queue='fila_consultas', durable=True)

    # Diz ao worker para consumir a fila usando a função callback
    channel.basic_consume(queue='fila_consultas', on_message_callback=callback)

    print("🚀 Worker pronto e escutando a fila! Pode mandar agendamentos.", flush=True)
    channel.start_consuming()

except Exception as e:
    print(f"❌ Erro fatal no Worker: {e}", flush=True)