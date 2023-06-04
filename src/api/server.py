from math import ceil
import time
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
        self.processedParts = {} # {jobID: {instrumento: {part_index: audio_part}}}
        self.musicReady = False

        # Rabbit MQ - Enviar não processadas
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', heartbeat=60, blocked_connection_timeout=10))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="music_parts")

        # Rabbit MQ - Receber processadas
        self.channel.queue_declare(queue="processed_parts")
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue="processed_parts", on_message_callback=self.receive_music_parts)

        self.num_parts = {} # musica -> num de partes

        self.startTime = {} #jobID - {part_index: time}
        self.time = {} #jobID - {part_index: time}

        self.size = {} #jobID - {part_index: size}

        self.jobslist = {} #jobID -> {part_index -> [size, time, music_id, track_id]}
        self.nJob = -1
        self.controlReceived = {} #jobID -> [part_index]

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
        return self.musicData[music_id]
    

    def listAll(self):
        return self.musicData
    
    def close(self):
        self.connection.close()


    def split_music(self, music_id: int, tracks_names: list):
        # Obter a música pelo id
        music = self.getMusic(music_id)
        self.nJob += 1
        self.jobslist[self.nJob] = {}
        self.startTime[self.nJob] = {}
        self.startTime[self.nJob] = {}
        self.time[self.nJob] = {}
        self.time[self.nJob] = {}
        self.size[self.nJob] = {}
        self.size[self.nJob] = {}

        # Carregar o arquivo de áudio
        audio = AudioSegment.from_file('static/unprocessed/00'+ str(music_id) + '_' + music.name + '.mp3', format='mp3')

        music = self.getMusic(music_id)
        duration = len(audio)  # Duração total da música em milissegundos
        part_duration = 10 * 1000  # Duração desejada de cada parte em milissegundos

        self.num_parts[music_id] = ceil(duration / part_duration)  # Calcular o número de partes arredondando para cima

        # Dividir a música em partes
        parts = [audio[i * part_duration: (i + 1) * part_duration] for i in range(self.num_parts[music_id])]

        for track in tracks_names:
            if self.nJob not in self.processedParts:
                self.processedParts[self.nJob] = {}  # Cria um dicionário vazio para a chave `music_id`
            self.processedParts[self.nJob][track] = {}  # Cria um dicionário vazio para a chave `track` dentro de `music_id`

        # Enviar as partes para a fila do RabbitMQ
        for i, part in enumerate(parts):
            output = BytesIO()
            part.export(output, format='mp3')
            part_data = {
                'music_id': music_id,
                'part_index': str(self.nJob) + "."+ str(i),
                'instruments': tracks_names,
                'part_audio': output.getvalue().decode('latin1')  # Converte os bytes em string
            }

            self.startTime[self.nJob][i] = time.time()
            self.size[self.nJob][i] = len(part_data['part_audio'])
            self.jobslist[self.nJob][i] = []
            self.connection.add_callback_threadsafe(lambda: self.send_music_part(part_data))

    def receive_music_parts(self, ch, method, properties, body):
        part_data = json.loads(body)
        music_id = part_data['music_id']
        part_index = part_data['part_index']
        part_audio = part_data['part_audio'].encode('latin1')  # Converte a string em bytes
        instrument = part_data['instrument']
        njob = int(part_index.split(".")[0])
        index = int(part_index.split(".")[1])

        self.time[njob][index] = time.time() - self.startTime[njob][index]

        if njob not in self.controlReceived:
            self.controlReceived[njob] = []
        
        if index not in self.controlReceived[njob]:
            self.controlReceived[njob].append(index)
            self.jobslist[njob][index] = [self.size[njob][index], self.time[njob][index], music_id, [instrument]]
        else:
            inst = self.jobslist[njob][index][-1]
            inst.append(instrument)
            self.jobslist[njob][index] = [self.size[njob][index], self.time[njob][index], music_id, inst]
        

        # Carregar a parte do áudio
        audio_part = AudioSegment.from_file(BytesIO(part_audio), format='wav')

        print(f' [x] Received part {index} of music {music_id} from job {njob} and the instrument is {instrument}')
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
        # Adicionar a parte do áudio ao dicionário
        self.processedParts[njob][instrument][index] = audio_part
        # Verificar se todas as partes já foram recebidas
        if len(self.processedParts[njob][instrument]) == self.num_parts[music_id]:
             self.join_music_parts(njob,music_id, instrument)


    def join_music_parts(self, njob, music_id, instrument):
        print(f' [*] Joining parts of music {music_id} from job {njob} and of instrument {instrument}')

        joinedParts = AudioSegment.empty()
        
        for i in range(self.num_parts[music_id]):
            joinedParts += self.processedParts[njob][instrument][i]
            
        joinedParts.export("static/processed/" + str(music_id) + "_" + instrument + ".wav", format="wav")

        self.musicReady = True

    def getInstrumentProgress(self, njob, music_id):
        instrumentProgress = {} # instrumento -> progresso (num partes já processadas/num partes)

        for instrument in self.processedParts[njob]:
            instrumentProgress[instrument] = len(self.processedParts[njob][instrument])/self.num_parts[music_id]

    def musicReady(self):
        return self.musicReady
    
    def getJobList(self):
        return self.jobslist
