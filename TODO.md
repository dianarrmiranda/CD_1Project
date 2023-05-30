## API:

uvicorn endpoints:app -- reload
porta: localhost:8000

## RabbitMQ:

docker ps -a p saber se ta up

Se n tiver, da up
Se n tiver imagem, cria com

docker pull rabbitmq:3-management
docker run --rm -it -p 15672:15672 -p 5672:5672 rabbitmq:3-management

porta: localhost:15672
user e pass: guest

https://fastapi.tiangolo.com/tutorial/first-steps/

https://medium.com/swlh/python-how-to-measure-thread-execution-time-in-multithreaded-application-f4b2e2112091

https://www.architect.io/blog/2021-01-19/rabbitmq-docker-tutorial/

https://www.rabbitmq.com/tutorials/tutorial-two-python.html

## Juntar áudios:

https://stackoverflow.com/questions/4039158/mixing-two-audio-files-together-with-python

def join_music_parts(self, tracks_to_join, music_folder):

        combined = AudioSegment.from_file(tracks_to_join[0])

        for track in tracks_to_join(1, len(tracks_to_join)):
            sound = AudioSegment.from_file(track)
            combined = combined.overlay(sound)

        combined.export(music_folder + "combined.wav", format='wav')
        

sound1 = AudioSegment.from_wav("/path/to/file1.wav")
sound2 = AudioSegment.from_wav("/path/to/file2.wav")

combined_sounds = sound1 + sound2
combined_sounds.export("/output/path.wav", format="wav")


 ## TODO ##
 Fazer parte do jobs
 Fault tolerance
 Mudar request body do post music/{music.id} para receber json da lista ids ao inves das strings dos instrumentos
 Dar fix da api toda pra ficar igual ao swagger do professor
 FEITO - Fazer ficheiro bash pra lançar os workers
 Testar separar em um número de partes baseado no tamanho da música ao invés de um valor fixo
 Consertar aparecer a música no frontend mesmo ela n estando lá