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

