import pickle
import subprocess
import time
import traceback
import pika
import json
from pydub import AudioSegment
from io import BytesIO
import demucs.separate
import os, sys, signal
import tempfile
import torch


class Worker:

    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('192.168.132.198'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="music_parts")
        self.channel.queue_declare(queue="processed_parts")
        # Consumir as partes da música da fila "music_parts"
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue="music_parts", on_message_callback=self.process_music_part)
        torch.set_num_threads(1)

        self.current_part_data = None
        
    
    def start(self):
        print(' [*] Waiting for music parts. To exit press CTRL+C')
        self.channel.start_consuming()

    def run_forever(self):
        while True:
            if not self.current_part_data:
                try:
                    self.start()
                except (Exception, KeyboardInterrupt) as e:
                    print("Worker encontrou um erro:", e)
                    print("Reiniciando o worker...")
                    time.sleep(1)
                    traceback.print_exc()
                    # Criar um novo canal
                    self.channel = self.connection.channel()
                    self.channel.queue_declare(queue="music_parts")
                    self.channel.queue_declare(queue="processed_parts")
                    self.channel.basic_qos(prefetch_count=1)
                    self.channel.basic_consume(queue="music_parts", on_message_callback=self.process_music_part)
            else:
                self.process_music_part(self.current_part_data[0], self.current_part_data[1], self.current_part_data[2], self.current_part_data[3])
                self.current_part_data = None

    def signal_handler(self, sig):
        print('\n [*] Worker done!')
        sys.exit(0)
    
    def send_processed_music_part(self, track, part_index, music_id):
        audio = AudioSegment.from_file("../tracks/" + str(music_id) + "/" + track, format='wav')
        output = BytesIO()
        audio.export(output, format='wav')
        part_data = {
                'music_id': music_id,
                'part_index': part_index,
                'instrument': track[:-6] if int(part_index.split(".")[1]) > 9 else track[:-5],
                'part_audio': output.getvalue().decode('latin1')  # Converte os bytes em string
            }
        
        self.channel.basic_publish(
            exchange='',
            routing_key='processed_parts',
            body=json.dumps(part_data)
        )

    def process_audio(self, audio_part, music_id, index):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        main_script = os.path.join(current_dir, '..', 'main.py')
        music_folder = os.path.join(current_dir, '..', 'tracks', str(music_id))

        if not os.path.exists(music_folder):
            os.makedirs(music_folder)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio_file:
            audio_part.export(temp_audio_file.name, format='mp3')
            temp_audio_path = temp_audio_file.name
        # Executar o arquivo main.py
        subprocess.run(['python3', main_script, '-i', temp_audio_path, '-o', music_folder, '-p' , str(index)])
        # Remover o arquivo temporário
        os.remove(temp_audio_path)


    def process_music_part(self, ch, method, properties, body):
        part_data = json.loads(body)
        self.current_part_data = [ch, method, properties, body]
        music_id = part_data['music_id']
        part_index = part_data['part_index']
        part_audio = part_data['part_audio'].encode('latin1')  # Converte a string em bytes
        tracks_names = part_data['instruments']
        i = part_index.split(".")
        index = int(i[1])
        # Carregar a parte do áudio
        audio_part = AudioSegment.from_file(BytesIO(part_audio), format='mp3')

        print(f' [x] Received part {index} of music {music_id}')

        ch.basic_ack(delivery_tag=method.delivery_tag)


        self.process_audio(audio_part, music_id, index)

        # Enviar partes processadas apenas dos instrumentos solicitados
        if index < 10:
            for track in os.listdir("../tracks/" + str(music_id)):
                if track[:-5] in tracks_names and int(track[-5]) == index:
                    self.send_processed_music_part(track, part_index, music_id)
                if (os.path.exists("../tracks/" + str(music_id) + "/" + (track[:-5] + str(index)) + ".wav")) and int(track[-5]) == index:
                    os.remove("../tracks/" + str(music_id) + "/" + (track[:-5] + str(index)) + ".wav")
        else:
            for track in os.listdir("../tracks/" + str(music_id)):
                if track[:-6] in tracks_names and int(track[-6:-4]) == index:
                    self.send_processed_music_part(track, part_index, music_id)
                if (os.path.exists("../tracks/" + str(music_id) + "/" + (track[:-6] + str(index)) + ".wav")) and int(track[-6:-4]) == index:
                    os.remove("../tracks/" + str(music_id) + "/" + (track[:-6] + str(index)) + ".wav")
                    
        self.current_part_data = None



worker = Worker()
worker.run_forever()  # Iniciar o processamento das partes da música
