from math import ceil
from schemas import Music
import pika
import signal, sys
from pydub import AudioSegment
import json
from io import BytesIO
import threading

class Server(threading.Thread):

    def __init__(self):

        # Threading
        super().__init__()
        self.deamon = True
        self.isRunning = True

        # Músicas a serem processadas
        self.musicData = []
        # Partes processadas
        self.instruments = ["drums", "bass", "vocals", "other"]
        # Partes processadas
        self.processedParts = {instrument: {} for instrument in self.instruments}

        # Rabbit MQ - Enviar não processadas
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', heartbeat=60, blocked_connection_timeout=10))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="music_parts")

        # Rabbit MQ - Receber processadas
        self.channel.queue_declare(queue="processed_parts")
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue="processed_parts", on_message_callback=self.receive_music_parts)

        self.num_parts = 0
    

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

        # Carregar o arquivo de áudio
        audio = AudioSegment.from_file('static/unprocessed/00'+ str(music_id) + '_' + music.name + '.mp3', format='mp3')

        music = self.getMusic(music_id)
        duration = len(audio)  # Duração total da música em milissegundos
        part_duration = 30 * 1000  # Duração desejada de cada parte em milissegundos

        self.num_parts = ceil(duration / part_duration)  # Calcular o número de partes arredondando para cima

        # Dividir a música em partes
        parts = [audio[i * part_duration: (i + 1) * part_duration] for i in range(self.num_parts)]

        # Adicionar ao dicionário
        for track in tracks_names:
            self.processedParts[track] = {}

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


    def receive_music_parts(self, ch, method, properties, body):

        part_data = json.loads(body)
        music_id = part_data['music_id']
        part_index = part_data['part_index']
        part_audio = part_data['part_audio'].encode('latin1')  # Converte a string em bytes
        instrument = part_data['instrument']

        # Carregar a parte do áudio
        audio_part = AudioSegment.from_file(BytesIO(part_audio), format='wav')

        print(f' [x] Received part {part_index} of music {music_id} and of instrument {instrument}')

        ch.basic_ack(delivery_tag=method.delivery_tag)

        # Verificar se a parte já foi recebida
        self.processedParts[instrument][part_index] = audio_part
        print("tamanho " + str(len(self.processedParts[instrument])))
        if len(self.processedParts[instrument]) == self.num_parts:
             self.join_music_parts(music_id, instrument)



    def join_music_parts(self, music_id, instrument):

        print(f' [*] Joining parts of music {music_id} and of instrument {instrument}')

        # Ordenar as partes do áudio por part_index
        sorted_parts = sorted(self.processedParts[instrument].items(), key=lambda x: x[0])

        # Juntar as partes do áudio
        joinedParts = sorted_parts[0][1]
        for _, part in sorted_parts[1:]:
            joinedParts += part

        # Salvar a música
        joinedParts.export("static/processed/" + str(music_id) + "_" + instrument + ".wav", format="wav")

