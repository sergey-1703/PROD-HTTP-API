import psycopg2
import pytz
import psycopg2.extensions
from datetime import datetime
from urllib.parse import urlparse
from passwordtools import hash_password
from models import ChangeProfileList, Post, PostInfo

connection: psycopg2.extensions.connection


def connect(uri: str):
    global connection
    result = urlparse(uri)
    username = result.username
    password = result.password
    database = result.path[1:]
    hostname = result.hostname
    port = result.port
    connection = psycopg2.connect(
        database=database,
        user=username,
        password=password,
        host=hostname,
        port=port
    )
    connection.autocommit = True


def connect_debug():
    global connection
    username = "postgres"
    password = ""
    database = "postgres"
    hostname = "localhost"
    port = "5432"
    connection = psycopg2.connect(
        database=database,
        user=username,
        password=password,
        host=hostname,
        port=port
    )
    connection.autocommit = True


def table_is_exists(table_name: str):
    cursor = connection.cursor()
    cursor.execute(f"select * from information_schema.tables where table_name= '{table_name}'")
    return bool(cursor.rowcount)


def create_tables():
    if not table_is_exists("profiles"):
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE profiles (
            login TEXT PRIMARY KEY,
            email TEXT,
            psd TEXT,
            countryCode TEXT,
            isPublic boolean,
            phone TEXT,
            image TEXT,
            friends TEXT[]
        );
        """)
    if not table_is_exists("tokenswhitelist"):
        cursor = connection.cursor()
        cursor.execute("""
                    CREATE TABLE tokenswhitelist(
                    token TEXT
                );
                """)
    if not table_is_exists("posts"):
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE posts (
            id SERIAL PRIMARY KEY,
            content TEXT,
            author TEXT,
            tags TEXT[],
            createdat TEXT,
            likes TEXT[],
            dislikes TEXT[]   
        );
        """)


def add_token_to_whitelist(token: str):
    connection.cursor().execute(f"""INSERT INTO tokenswhitelist (token) values ('{token}')""")


def remove_token_from_whitelist(token: str):
    connection.cursor().execute(f"""DELETE FROM tokenswhitelist WHERE token = ('{token}')""")


def add_post(post: Post, login: str):
    create_time = datetime.utcnow().replace(tzinfo=pytz.utc).strftime("%m/%d/%Y, %H:%M:%SZ")
    output = PostInfo(id="0", content=post.content, author=login, tags=post.tags, createdAt=create_time, likesCount=0, dislikesCount=0)
    cursor = connection.cursor()
    cursor.execute(f"""INSERT INTO posts (content, author, tags, createdat) values ('{post.content}', '{login}', ARRAY{post.tags}, 
        '{create_time}') RETURNING id""")
    output.id = str(cursor.fetchone()[0])
    return output


def get_post(ids: str) -> PostInfo | None:
    cursor = connection.cursor()
    cursor.execute(f"""SELECT * from posts WHERE id = {ids}""")
    data = cursor.fetchone()
    if data is None:
        return None
    return PostInfo(id=str(data[0]), content=data[1], author=data[2], tags=data[3], createdAt=data[4], likesCount=len(data[5]) if data[5] is not None else 0, dislikesCount=len(data[6]) if data[6] is not None else 0)


def get_posts_by_login(login: str) -> [PostInfo]:
    cursor = connection.cursor()
    cursor.execute(f"""SELECT * from posts WHERE author = '{login}'""")
    data = cursor.fetchall()
    if len(data) == 0:
        return None
    arr = []
    for i in data:
        arr.append(PostInfo(id=str(i[0]), content=i[1], author=i[2], tags=i[3], createdAt=i[4], likesCount=len(i[5]) if i[5] is not None else 0, dislikesCount=len(i[6]) if i[6] is not None else 0))
    return arr


def post_is_existed(ids: str) -> bool:
    cursor = connection.cursor()
    cursor.execute(f"""SELECT * from posts WHERE id = {ids}""")
    return cursor.fetchone() is not None


def token_is_in_whitelist(token: str):
    cursor = connection.cursor()
    cursor.execute(f"""SELECT * FROM tokenswhitelist WHERE token = '{token}'""")
    return cursor.fetchone() is not None


def create_user(login: str, email: str, password: str, country_code: str, is_public: bool, phone: str, image: str):
    connection.cursor().execute(f"""INSERT INTO profiles (login, email, psd, countrycode, ispublic,
     phone, image) values ('{login}', '{email}', '{str(hash_password(password))[2:-1]}', 
     '{country_code}', '{is_public}', '{phone}', '{image}')""")


def update_user(login: str, changeList: ChangeProfileList):
    update_str = ""
    if changeList.countryCode is not None:
        update_str += f"countryCode = '{ changeList.countryCode}',"
    if changeList.isPublic is not None:
        update_str += f"ispublic = { changeList.isPublic},"
    if changeList.phone is not None:
        update_str += f"phone = '{ changeList.phone}',"
    if changeList.image is not None:
        update_str += f"image = '{changeList.image}',"
    connection.cursor().execute(f"""UPDATE profiles SET {update_str[:-1]} WHERE login = '{login}'""")


def set_like(id, login: str):
    code = 0
    cursor = connection.cursor()
    cursor.execute(f"""SELECT * FROM posts WHERE '{login}' = ANY(likes) and id = '{id}'""")
    if cursor.fetchone() is None:
        cursor.execute(f"""UPDATE posts SET likes = array_append(likes, '{login}') WHERE id = {id}""")
        cursor.execute(f"""SELECT * FROM posts WHERE '{login}' = ANY(dislikes) and id = '{id}'""")
        code = 1
        if cursor.fetchone() is not None:
            cursor.execute(f"""UPDATE posts SET dislikes = array_remove(dislikes, '{login}') WHERE id = {id}""")
            code = 2
        return code
    return code


def set_dislike(id, login: str):
    code = 0
    cursor = connection.cursor()
    cursor.execute(f"""SELECT * FROM posts WHERE '{login}' = ANY(dislikes) and id = '{id}'""")
    if cursor.fetchone() is None:
        cursor.execute(f"""UPDATE posts SET dislikes = array_append(dislikes, '{login}') WHERE id = {id}""")
        cursor.execute(f"""SELECT * FROM posts WHERE '{login}' = ANY(likes) and id = '{id}'""")
        code = 1
        if cursor.fetchone() is not None:
            cursor.execute(f"""UPDATE posts SET likes = array_remove(likes, '{login}') WHERE id = {id}""")
            code = 2
        return code
    return code


def get_user_by_propety(property: str, value: str):
    cursor = connection.cursor()
    cursor.execute(f"SELECT * FROM profiles WHERE {property} = '{value}'")
    data = cursor.fetchone()
    return data


def update_user_password(login: str, password: str):
    connection.cursor().execute(f"""UPDATE profiles SET psd = '{str(hash_password(password))[2:-1]}' WHERE login = '{login}'""")


def add_friend(request_author_login: str, friend_login: str):
    cursor = connection.cursor()
    cursor.execute(f"""UPDATE profiles SET friends = array_append(friends,'{friend_login}') WHERE login = '{request_author_login}'""")
    cursor.execute(
        f"""UPDATE profiles SET friends = array_append(friends,'{datetime.utcnow().replace(tzinfo=pytz.utc).strftime("%m/%d/%Y, %H:%M:%SZ")}') WHERE login = '{request_author_login}'""")
    cursor.execute(f"""UPDATE profiles SET friends = array_append(friends,'{request_author_login}') WHERE login = '{friend_login}'""")
    cursor.execute(
        f"""UPDATE profiles SET friends = array_append(friends,'{datetime.utcnow().replace(tzinfo=pytz.utc).strftime("%m/%d/%Y, %H:%M:%SZ")}') WHERE login = '{friend_login}'""")


def remove_friend(request_author_login: str, friend_login: str):
    cursor = connection.cursor()
    cursor.execute(f"""SELECT array_position(friends, '{friend_login}') FROM profiles WHERE login = '{request_author_login}'""")
    l_id = cursor.fetchone()[0]
    cursor.execute(f"""UPDATE profiles SET friends = array_remove(friends,'{friend_login}') WHERE login = '{request_author_login}'""")
    cursor.execute(f"""UPDATE profiles SET friends = array_remove(friends, friends[{l_id}]) WHERE login = '{request_author_login}'""")
    cursor.execute(f"""SELECT array_position(friends, '{request_author_login}') FROM profiles WHERE login = '{friend_login}'""")
    l_id = cursor.fetchone()[0]
    cursor.execute(f"""UPDATE profiles SET friends = array_remove(friends,'{request_author_login}') WHERE login = '{friend_login}'""")
    cursor.execute(f"""UPDATE profiles SET friends = array_remove(friends, friends[{l_id}]) WHERE login = '{friend_login}'""")


def friend_is_in_friends(request_login: str, friend: str):
    cursor = connection.cursor()
    cursor.execute(f"""SELECT * FROM profiles WHERE '{friend}' = ANY(friends) and login = '{request_login}'""")
    return cursor.fetchone() is not None


def user_property_is_exists(property: str, value: str):
    return get_user_by_propety(property, value) is not None


def get_friends(login: str):
    cursor = connection.cursor()
    cursor.execute(f"""SELECT friends from profiles WHERE login = '{login}'""")
    data = cursor.fetchall()
    arr = []
    for i in data:
        for t in i:
            if t is None:
                return []
            for x in t:
                arr.append(x)
    return list(reversed(arr))


def get_countries(regions: [str]):
    cursor = connection.cursor()
    if regions is None:
        cursor.execute("SELECT * FROM countries")
    else:
        query = ""
        l_i = len(regions) - 1
        for i in range(l_i + 1):
            if i == l_i:
                query += f"region = '{regions[i]}'"
            else:
                query += f"region = '{regions[i]}' or "
        cursor.execute(f"SELECT * FROM countries WHERE {query}")
    res = []
    for con in cursor.fetchall():
        res.append(con[1:])
    return res


def get_countries_with_code(code: str):
    cursor = connection.cursor()
    cursor.execute(f"SELECT * FROM countries WHERE alpha2 = '{code.upper()}'")
    data = cursor.fetchone()
    if data is None:
        return None
    return data[1:]

