import subprocess
import pika
import json
from pydub import AudioSegment
from io import BytesIO
import demucs.separate
import os
import tempfile
import torch


class Worker:

    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="music")
        self.channel.queue_declare(queue="music_parts")

        # Consumir as partes da música da fila "music_parts"
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue="music_parts", on_message_callback=self.process_music_part)
        torch.set_num_threads(1)
        
    def start(self):
        print(' [*] Waiting for music parts. To exit press CTRL+C')
        self.channel.start_consuming()


    def process_music_part(self, ch, method, properties, body):
        part_data = json.loads(body)
        music_id = part_data['music_id']
        part_index = part_data['part_index']
        part_audio = part_data['part_audio'].encode('latin1')  # Converte a string em bytes

        # Carregar a parte do áudio
        audio_part = AudioSegment.from_file(BytesIO(part_audio), format='mp3')

        print(f' [x] Received part {part_index} of music {music_id}')

        ch.basic_ack(delivery_tag=method.delivery_tag)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        main_script = os.path.join(current_dir, '..', 'main.py')
        music_folder = os.path.join(current_dir, '..', 'tracks', str(music_id))

        if not os.path.exists(music_folder):
            os.makedirs(music_folder)

        # Salvar a parte do áudio em um arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio_file:
            audio_part.export(temp_audio_file.name, format='mp3')
            temp_audio_path = temp_audio_file.name
        # Executar o arquivo main.py
        subprocess.run(['python3', main_script, '-i', temp_audio_path, '-o',music_folder, '-p' , str(part_index)])
        
        # Remover o arquivo temporário
        os.remove(temp_audio_path)



worker = Worker()
worker.start()  # Iniciar o processamento das partes da música
