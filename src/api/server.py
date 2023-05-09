from schemas import Music
import pika
import signal, sys

class Server:

    def __init__(self):
        self.musicData = []
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="music")
    
    def sendMsg(self):
        self.channel.basic_publish(exchange='', routing_key='hello', body='Hello World!')
  
    
    def addMusic(self, music):
        self.musicData.append(music)


    def getMusic(self, music_id):
        return self.musicData[music_id]
    

    def listAll(self):
        return self.musicData
    
    def close(self):
        self.connection.close()
