from math import ceil
import os, sys
import time
import pika
from pydub import AudioSegment
import json
from io import BytesIO
import threading

class Server(threading.Thread):

    def __init__(self):

        # Threading
        super().__init__()
        self.daemon = True
        self.isRunning = True

        self.musicData = []
        self.processedParts = {} # {musicID: {instrumento: {part_index: audio_part}}}
        self.num_parts = {} # musicID -> num de partes
        self.tracks = {} # job_id -> [instrumentos]
        self.startTime = {} #musicId - {part_index: time}
        self.time = {} #musicId - {part_index: time}
        self.size = {} #musicId - {part_index: size}
        self.jobslist = {} #nJob -> {part_index -> [size, time, music_id, track_id[tracks] ]}
        self.nJob = -1
        self.control = -1

        self.progress = {} #musicID -> [progress, [instruments], final]
        self.jobProgress = {} #jobId -> numero de partes recebidas
    
        # Rabbit MQ - Enviar não processadas
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', heartbeat=60, blocked_connection_timeout=10))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="music_parts")
        # Rabbit MQ - Receber processadas
        self.channel.queue_declare(queue="processed_parts")
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue="processed_parts", on_message_callback=self.receive_music_parts)



    def run(self):
        while self.isRunning:
            self.connection.process_data_events(time_limit=1)


    def stop(self):
        print(' [*] Stopping server...')

        self.isRunning = False
        self.connection.process_data_events(time_limit=1)
        self.clear_directory("static/unprocessed")
        self.clear_directory("static/processed")

        if self.connection.is_open:
            self.connection.close()
        print(' [*] Server stopped')


    def clear_directory(self, directory):
        for f in os.listdir(directory):
            os.remove(os.path.join(directory, f))


    def send_music_part(self, part_data):
        self.channel.basic_publish(
            exchange='',
            routing_key='music_parts',
            body=json.dumps(part_data)
        )


    def addMusic(self, music):
        self.musicData.append(music)
        self.jobslist[music.music_id] = {}
        self.startTime[music.music_id] = {}
        self.time[music.music_id] = {}
        self.size[music.music_id] = {}
        self.progress[music.music_id] = [0, [], '']


    def getMusic(self, music_id):
        return self.musicData[music_id]


    def listAll(self):
        return self.musicData
    

    def split_music(self, music_id: int, tracks_names: list):
        self.nJob += 1
        self.jobslist[self.nJob] = {} 
        self.tracks[self.nJob] = tracks_names.copy()
        self.jobProgress[self.nJob] = 0

        music = self.getMusic(music_id)

        # Carregar o arquivo de áudio
        audio = AudioSegment.from_file('static/unprocessed/00'+ str(music_id) + '_' + music.name + '.mp3', format='mp3')
        duration = len(audio)  # Duração total da música em milissegundos
        part_duration = 10 * 1000  # Duração desejada de cada parte em milissegundos
        self.num_parts[music_id] = ceil(duration / part_duration)  # Calcular o número de partes arredondando para cima

        # Dividir a música em partes
        parts = [audio[i * part_duration: (i + 1) * part_duration] for i in range(self.num_parts[music_id])]

        for track in self.tracks[self.nJob]:
            if music_id not in self.processedParts:
                self.processedParts[music_id] = {}  # Cria um dicionário vazio para a chave `music_id`
            if track not in self.processedParts[music_id].keys():
                self.processedParts[music_id][track] = {}  # Cria um dicionário vazio para a chave `track` dentro de `music_id`
            else:
                print(' [*] Track ' + track + ' already processed')
                self.jobProgress[self.nJob] += 1
                tracks_names.remove(track)  # Remove o instrumento da lista de instrumentos a serem processados

        if len(tracks_names) > 0:
        # Enviar as partes para a fila do RabbitMQ
            for i, part in enumerate(parts):
                output = BytesIO()
                part.export(output, format='mp3')
                part_data = {
                    'music_id': music_id,
                    'part_index': i,
                    'instruments': tracks_names,
                    'part_audio': output.getvalue().decode('latin1'),  # Converte os bytes em string
                    'njob': self.nJob
                }

                self.startTime[music_id][i] = time.time()
                self.size[music_id][i] = len(part_data['part_audio'])
                self.connection.add_callback_threadsafe(lambda: self.send_music_part(part_data))
        else:
            if (self.progress[music_id] == 100):
                self.joinInstruments(music_id, self.nJob)
        
        self.jobProgress[self.nJob] *= self.num_parts[music_id]
        self.progress[music_id][0] = (100*self.jobProgress[self.nJob])/(self.num_parts[music_id] * len(self.tracks[self.nJob]))

    def receive_music_parts(self, ch, method, properties, body):
        part_data = json.loads(body)
        music_id = part_data['music_id']
        part_index = part_data['part_index']
        part_audio = part_data['part_audio'].encode('latin1')  # Converte a string em bytes
        instrument = part_data['instrument']
        njob = part_data['njob']

        if(self.jobProgress == {}):
            return

        if(self.jobProgress[njob] < self.num_parts[music_id]*len(self.tracks[njob])):
            self.jobProgress[njob] +=1 
        
        self.progress[music_id][0] = (100*self.jobProgress[njob])/(self.num_parts[music_id] * len(self.tracks[njob]))

        self.time[music_id][part_index] = time.time() - self.startTime[music_id][part_index]

        if part_index not in self.jobslist[njob]:
            self.jobslist[njob][part_index] = [self.size[music_id][part_index], self.time[music_id][part_index], music_id, [instrument]]
        else:
            inst = self.jobslist[njob][part_index][-1]
            inst.append(instrument)
            self.jobslist[njob][part_index] = [self.size[music_id][part_index], self.time[music_id][part_index], music_id, inst]
        
        # Carregar a parte do áudio
        audio_part = AudioSegment.from_file(BytesIO(part_audio), format='wav')

        print(f' [x] Received part {part_index} of music {music_id} and the instrument is {instrument}')
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
        # Adicionar a parte do áudio ao dicionário
        self.processedParts[music_id][instrument][part_index] = audio_part
        # Verificar se todas as partes já foram recebidas
        if len(self.processedParts[music_id][instrument]) == self.num_parts[music_id]:
             self.join_music_parts(music_id, instrument, njob)

    def join_music_parts(self, music_id, instrument, njob):
        print(f' [*] Joining parts of music {music_id} and of instrument {instrument}')

        joinedParts = AudioSegment.empty()
        
        for i in range(self.num_parts[music_id]):
            joinedParts += self.processedParts[music_id][instrument][i]
            
        joinedParts.export("static/processed/" + str(music_id) + "_" + instrument + ".wav", format="wav")

        self.progress[music_id][1].append([instrument, '/static/processed/{}_{}.wav'.format(music_id, instrument)])

        if(self.jobProgress[njob]/self.num_parts[music_id]) == len(self.tracks[njob]):
            self.joinInstruments(music_id, njob)


    def joinInstruments(self, music_id, njob):
        print(f' [*] Joining instruments of music {music_id}')

        instruments = self.tracks[njob]
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
        self.jobslist = {}
        self.startTime = {}
        self.time = {}
        self.size = {}
        self.processedParts = {}
        self.num_parts = {}
        self.nJob = -1
        self.musicData = []
        self.tracks = {}
        self.jobProgress = {}
        self.progress = {}

        self.isRunning = False
        self.connection.process_data_events(time_limit=1)
        self.clear_directory("static/unprocessed")
        self.clear_directory("static/processed")
        self.channel.queue_delete(queue="music_parts")
        self.channel.queue_delete(queue="processed_parts")

        print("[*] Resetting...")
        time.sleep(40)

        print(' [*] Reseted all data')
