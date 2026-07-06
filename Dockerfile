FROM python:3.12.1-alpine3.19

WORKDIR /source

COPY requirements.txt requirements.txt
# install psycopg2 dependencies
RUN apk update
RUN apk add postgresql-dev gcc python3-dev musl-dev
RUN pip3 install -r requirements.txt

COPY ./source /source

ENV SERVER_PORT=8080

# CMD ["sh", "-c", "exec python3 -m flask run --host=0.0.0.0 --port=$SERVER_PORT"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]