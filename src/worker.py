import subprocess
import time
import traceback
import pika
import json
from pydub import AudioSegment
from io import BytesIO
import os, sys
import tempfile
import torch


class Worker:

    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="music_parts")
        self.channel.queue_declare(queue="processed_parts")
        # Consumir as partes da música da fila "music_parts"
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue="music_parts", on_message_callback=self.process_music_part)
        torch.set_num_threads(1)
    
    def start(self):
        print(' [*] Waiting for music parts.')
        self.channel.start_consuming()

    def signal_handler(self, sig):
        print('\n [*] Worker done!')
        sys.exit(0)
    
    def send_processed_music_part(self, track, part_index, music_id, njob):
        audio = AudioSegment.from_file("../tracks/" + str(music_id) + "/" + track, format='wav')
        output = BytesIO()
        audio.export(output, format='wav')

        instrument = ''
        if part_index > 9 and part_index < 100:
            instrument = track[:-6]
        elif part_index > 99:
            instrument = track[:-7]
        else:
            instrument = track[:-5]
        part_data = {
            'music_id': music_id,
            'part_index': part_index,
            'instrument': instrument,
            'part_audio': output.getvalue().decode('latin1'),
            'njob': njob
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
        subprocess.run(['python3', main_script, '-i', temp_audio_path, '-o', music_folder, '-p', str(index)])
        # Remover o arquivo temporário
        os.remove(temp_audio_path)


    def process_music_part(self, ch, method, properties, body):
        part_data = json.loads(body)
        music_id = part_data['music_id']
        part_index = part_data['part_index']
        part_audio = part_data['part_audio'].encode('latin1')  # Converte a string em bytes
        tracks_names = part_data['instruments']
        njob = part_data['njob']
        # Carregar a parte do áudio
        audio_part = AudioSegment.from_file(BytesIO(part_audio), format='mp3')

        print(f' [x] Received part {part_index} of music {music_id}')

        try:
            self.process_audio(audio_part, music_id, part_index)

            # Enviar partes processadas apenas dos instrumentos solicitados
            if part_index < 10:
                for track in os.listdir("../tracks/" + str(music_id)):
                    if track[:-5] in tracks_names and int(track[-5]) == part_index:
                        self.send_processed_music_part(track, part_index, music_id,njob)
                    if (os.path.exists("../tracks/" + str(music_id) + "/" + (track[:-5] + str(part_index)) + ".wav")) and int(track[-5]) == part_index:
                        os.remove("../tracks/" + str(music_id) + "/" + (track[:-5] + str(part_index)) + ".wav")
            elif part_index < 100:
                for track in os.listdir("../tracks/" + str(music_id)):
                    if track[:-6] in tracks_names and int(track[-6:-4]) == part_index:
                        self.send_processed_music_part(track, part_index, music_id, njob)
                    if (os.path.exists("../tracks/" + str(music_id) + "/" + (track[:-6] + str(part_index)) + ".wav")) and int(track[-6:-4]) == part_index:
                        os.remove("../tracks/" + str(music_id) + "/" + (track[:-6] + str(part_index)) + ".wav")
            else:
                for track in os.listdir("../tracks/" + str(music_id)):
                    if track[:-7] in tracks_names and int(track[-7:-4]) == part_index:
                        self.send_processed_music_part(track, part_index, music_id, njob)
                    if (os.path.exists("../tracks/" + str(music_id) + "/" + (track[:-7] + str(part_index)) + ".wav")) and int(track[-7:-4]) == part_index:
                        os.remove("../tracks/" + str(music_id) + "/" + (track[:-7] + str(part_index)) + ".wav")

            # Enviar confirmação de recebimento (basic_ack) após a conclusão bem-sucedida do processamento
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(f"Erro ao processar a parte {part_index} da música {music_id}: {e}")
            # Retornar a parte da música à fila para ser processada novamente
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


worker = Worker()
worker.start()  # Iniciar o processamento das partes da música
