from dataclasses import dataclass
from os import getenv


@dataclass
class Config:
    server_address: str
    server_port: str
    postgres_conn: str
    postgres_jbdc_url: str
    postgres_username: str
    postgres_password: str
    postgres_host: str
    postgres_post: str
    postgres_database: str


def load_config():
    return Config(server_address=getenv('SERVER_ADDRESS'), server_port=getenv('SERVER_PORT'),
                  postgres_conn=getenv('POSTGRES_CONN'), postgres_jbdc_url=getenv('POSTGRES_JDBC_URL'),
                  postgres_username=getenv('POSTGRES_USERNAME'), postgres_password=getenv('POSTGRES_PASSWORD'),
                  postgres_host=getenv('POSTGRES_HOST'), postgres_post=getenv('POSTGRES_PORT'),
                  postgres_database=getenv('POSTGRES_DATABASE'))
