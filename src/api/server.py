from math import ceil
import os
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
        self.processedParts = {} # {musicID: {instrumento: {part_index: audio_part}}}

        # Rabbit MQ - Enviar não processadas
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', heartbeat=60, blocked_connection_timeout=10))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="music_parts")

        # Rabbit MQ - Receber processadas
        self.channel.queue_declare(queue="processed_parts")
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue="processed_parts", on_message_callback=self.receive_music_parts)

        self.num_parts = {} # musicID -> num de partes
        self.tracks = {} # musicID -> [instrumentos]

        self.startTime = {} #musicId - {part_index: time}
        self.time = {} #musicId - {part_index: time}

        self.size = {} #musicId - {part_index: size}

        self.jobslist = {} #nJob -> {part_index -> [size, time, music_id, track_id[tracks] ]}
        self.nJob = -1
        self.countParts = {} #jobID -> {count}

        self.controlReceived = {} #musicId -> [part_index]
        self.controlWorkers = {} #musicId -> {part_index -> partData} 
        self.ctrWork = 0

        self.progress = {} #musicID -> {progress}
        self.jobProgress = {} #musicId -> numero de partes recebidas

    def run(self):
        while self.isRunning:
            self.connection.process_data_events(time_limit=1)


    def stop(self):
        print(' [*] Stopping server...')
        self.isRunning = False
        self.connection.process_data_events(time_limit=1)

        dir = "static/unprocessed"
        for f in os.listdir(dir):
            os.remove(os.path.join(dir, f))

        dir = "static/processed"
        for f in os.listdir(dir):
            os.remove(os.path.join(dir, f)) 
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
        self.jobslist[music_id] = {}
        self.startTime[music_id] = {}
        self.time[music_id] = {}
        self.size[music_id] = {}
        self.controlWorkers[music_id] = {}
        self.countParts[music_id] = 0
        self.jobProgress[music_id] = 0
        self.progress[music_id] = [0, [], '']
        self.tracks[music_id] = tracks_names
        self.nJob += 1
        self.jobslist[self.nJob] = {}  

        # Carregar o arquivo de áudio
        audio = AudioSegment.from_file('static/unprocessed/00'+ str(music_id) + '_' + music.name + '.mp3', format='mp3')

        music = self.getMusic(music_id)
        duration = len(audio)  # Duração total da música em milissegundos
        part_duration = 10 * 1000  # Duração desejada de cada parte em milissegundos
        total_duration_sec = duration / 1000  # Converter a duração total da música para segundos

        self.timeout = 2 * total_duration_sec  # Ajustar o valor do timeout com base na duração da música

        self.num_parts[music_id] = ceil(duration / part_duration)  # Calcular o número de partes arredondando para cima

        # Dividir a música em partes
        parts = [audio[i * part_duration: (i + 1) * part_duration] for i in range(self.num_parts[music_id])]

        for track in tracks_names:
            if music_id not in self.processedParts:
                self.processedParts[music_id] = {}  # Cria um dicionário vazio para a chave `music_id`
            self.processedParts[music_id][track] = {}  # Cria um dicionário vazio para a chave `track` dentro de `music_id`

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

            self.controlWorkers[music_id][i] = part_data

            self.startTime[music_id][i] = time.time()
            self.size[music_id][i] = len(part_data['part_audio'])

            self.connection.add_callback_threadsafe(lambda: self.send_music_part(part_data))
        
        self.start_timeout(music_id)

    
    def start_timeout(self, music_id):
        timer = threading.Timer(self.timeout, lambda: self.check_and_resend_missing_parts(music_id))
        timer.start()


    def check_and_resend_missing_parts(self, music_id):
        missing_parts = []


        print("Control Received")
        print(self.controlReceived)

        for part_index in range(self.num_parts[music_id]):
            if part_index not in self.controlReceived[music_id]:
                missing_parts.append(part_index)

        

        for missing_part in missing_parts:
            part_data = self.controlWorkers[music_id][missing_part]
            self.startTime[music_id][missing_part] = time.time()
            self.size[music_id][missing_part] = len(part_data['part_audio'])
            self.connection.add_callback_threadsafe(lambda: self.send_music_part(part_data))


    def receive_music_parts(self, ch, method, properties, body):        
        part_data = json.loads(body)
        music_id = part_data['music_id']
        part_index = part_data['part_index']
        part_audio = part_data['part_audio'].encode('latin1')  # Converte a string em bytes
        instrument = part_data['instrument']

        if(self.jobProgress[music_id] < self.num_parts[music_id]*len(self.tracks[music_id])):
            self.jobProgress[music_id] +=1 
        
        self.progress[music_id][0] = (100*self.jobProgress[music_id])/(self.num_parts[music_id] * len(self.tracks[music_id]))

        self.time[music_id][part_index] = time.time() - self.startTime[music_id][part_index]

        if music_id not in self.controlReceived:
            self.controlReceived[music_id] = []
        
        if part_index not in self.controlReceived[music_id]:
            self.controlReceived[music_id].append(part_index)
            self.jobslist[self.nJob][part_index] = [self.size[music_id][part_index], self.time[music_id][part_index], music_id, [instrument]]
        else:
            inst = self.jobslist[self.nJob][part_index][-1]
            inst.append(instrument)
            self.jobslist[self.nJob][part_index] = [self.size[music_id][part_index], self.time[music_id][part_index], music_id, inst]
        
        if self.ctrWork < self.nJob:
           self.start_timeout(music_id)
           self.ctrWork = self.nJob
        
        # Carregar a parte do áudio
        audio_part = AudioSegment.from_file(BytesIO(part_audio), format='wav')

        print(f' [x] Received part {part_index} of music {music_id} and the instrument is {instrument}')
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
        # Adicionar a parte do áudio ao dicionário
        self.processedParts[music_id][instrument][part_index] = audio_part
        # Verificar se todas as partes já foram recebidas
        if len(self.processedParts[music_id][instrument]) == self.num_parts[music_id]:
             self.join_music_parts(music_id, instrument)


    def join_music_parts(self, music_id, instrument):
        print(f' [*] Joining parts of music {music_id} and of instrument {instrument}')

        joinedParts = AudioSegment.empty()
        
        for i in range(self.num_parts[music_id]):
            joinedParts += self.processedParts[music_id][instrument][i]
            
        joinedParts.export("static/processed/" + str(music_id) + "_" + instrument + ".wav", format="wav")

        self.countParts[music_id] += 1

        self.progress[music_id][1].append([instrument, '/static/processed/{}_{}.wav'.format(music_id, instrument)])


        if(self.countParts[music_id] == len(self.tracks[music_id])):
            self.joinInstruments(music_id)


    def joinInstruments(self, music_id):
        print(f' [*] Joining instruments of music {music_id}')

        instruments = self.jobslist[music_id][0][-1]
        joinedParts = AudioSegment.from_wav("static/processed/" + str(music_id) + "_" + instruments[0] + ".wav")
        inst = "_" + instruments[0]

        for i in range(1,len(instruments)):
            joinedParts = joinedParts.overlay(AudioSegment.from_wav("static/processed/" + str(music_id) + "_" + instruments[i] + ".wav"))
            inst += "_" + instruments[i] 

        joinedParts.export("static/processed/" + str(music_id) + inst + ".wav", format="wav")

        self.progress[music_id][2] = '/static/processed/{}{}.wav'.format(music_id, inst)
            

    def getProgress(self, music_id):
        return self.progress[music_id]

    def getJobList(self):
        count = 0
        allJobs = {}
        for key, job in self.jobslist.items():
            for sub_key, value in job.items():
                allJobs[count] = value
                count += 1

        return allJobs


    def reset(self):

        self.workerStatus = {} 
        self.jobslist = {}
        self.startTime = {}
        self.time = {}
        self.size = {}
        self.processedParts = {}
        self.controlReceived = {}
        self.num_parts = {}
        self.nJob = -1
        self.musicData = []
        self.controlWorkers = {}
        self.ctrWork = -1
        self.countParts = {}  


        dir = "static/unprocessed"
        for f in os.listdir(dir):
            os.remove(os.path.join(dir, f))

        dir = "static/processed"
        for f in os.listdir(dir):
            os.remove(os.path.join(dir, f)) 

        if self.connection.is_open:
            self.channel.queue_purge(queue="music_parts")
            self.channel.queue_purge(queue="processed_parts")