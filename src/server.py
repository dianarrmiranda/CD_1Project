from api.schemas import Music


class Server:

    def __init__(self):
        self.musicData = []

    def addMusic(self, music):
        self.musicData.append(music)

    def getMusic(self, music_id):
        return self.musicData[music_id]
    
    def listAll(self):
        return self.musicData