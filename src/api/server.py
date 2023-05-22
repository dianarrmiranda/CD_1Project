from schemas import Music
import pika
import signal, sys
from pydub import AudioSegment
import json
from io import BytesIO
from fastapi.staticfiles import StaticFiles
import threading

class Server(threading.Thread):

    def __init__(self):
        super().__init__()
        self.musicData = []
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', heartbeat=60, blocked_connection_timeout=10))
        self.deamon = True
        self.isRunning = True
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="processed_parts")
        self.channel.queue_declare(queue="music_parts")

        # Consumir as partes da música da fila "processed_parts"
        #self.channel.basic_qos(prefetch_count=1)
        #self.channel.basic_consume(queue="music_parts", on_message_callback=self.process_music_part)
    

    def run(self):
        while self.isRunning:
            self.connection.process_data_events(time_limit=1)


    def stop(self):
        print(' [*] Stopping server...')
        self.isRunning = False
        self.connection.process_data_events(time_limit=1)
        if self.connection.is_open:
            self.connection.close()
        print(' [*] Server stopped')
    

    def send_music_part(self, part_data):
        self.channel.basic_publish(
            exchange='',
            routing_key='music_parts',
            body=json.dumps(part_data)
        )

    
    def addMusic(self, music):
        self.musicData.append(music)


    def getMusic(self, music_id):
        print(self.musicData)
        return self.musicData[music_id]
    

    def listAll(self):
        return self.musicData
    
    def close(self):
        self.connection.close()


    def split_music(self, music_id: int, tracks_names: list):
        # Obter a música pelo id
        music = self.getMusic(music_id)
        num_parts = 4

        # Carregar o arquivo de áudio
        audio = AudioSegment.from_file('static/00'+ str(music_id) + '_' + music.name + '.mp3', format='mp3')

        # Calcular a duração de cada parte
        part_duration = len(audio) // num_parts

        # Dividir a música em partes
        parts = [audio[i * part_duration: (i + 1) * part_duration] for i in range(num_parts)]

        # Enviar as partes para a fila do RabbitMQ
        for i, part in enumerate(parts):
            output = BytesIO()
            part.export(output, format='mp3')
            part_data = {
                'music_id': music_id,
                'part_index': i,
                'instruments': tracks_names,
                'part_audio': output.getvalue().decode('latin1')  # Converte os bytes em string
            }
            
            self.connection.add_callback_threadsafe(lambda: self.send_music_part(part_data))



