from typing import List
import bcrypt
import pytz
from fastapi import FastAPI, status, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Annotated
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordBearer
from models import *
import database, jwt
from jwt import PyJWTError
from config import load_config
from validation import *
from datetime import datetime, timezone, timedelta
from pyrfc3339 import generate


app = FastAPI()
cfg = load_config()
database.connect(cfg.postgres_conn)
# database.connect_debug()
database.create_tables()

regions = ["", "Europe", "Africa", "Americas", "Oceania", "Asia"]
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
SECRET_KEY = "secret"
ALGORITHM = "HS256"


@app.get("/api/ping", status_code=200)
async def get_ping():
    return {"text": "ok"}


@app.get("/api/countries")
async def get_countries(region: List[str] = Query(None)):
    try:
        if region is not None and not all(regions.count(x) == 1 for x in region):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"reason": "Фильтр неверный"}
            )
        data = database.get_countries(region)
        data = sorted(data, key=lambda x: x[1])
        countries = []
        for c in data:
            countries.append(Country(name=c[0], alpha2=c[1], alpha3=c[2], region=c[3]))
        return JSONResponse(jsonable_encoder(countries))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/countries/{alpha2}")
async def get_countries_with_code(alpha2: str):
    try:
        data = database.get_countries_with_code(alpha2)
        if data is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"reason": "Страна не найдена"}
            )
        return JSONResponse(jsonable_encoder(Country(name=data[0], alpha2=data[1], alpha3=data[2], region=data[3])))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/register")
async def create_profile(profile: Profile):
    try:
        if not password_is_correct(profile.password):
            return JSONResponse(
                status_code=400,
                content={"reason": "Пароль некорректен"}
            )
        if not login_is_correct(profile.login):
            return JSONResponse(
                status_code=400,
                content={"reason": "Логин некорректен"}
            )
        if profile.phone is not None and not phone_is_correct(profile.phone):
            return JSONResponse(
                status_code=400,
                content={"reason": "Номер телефона некорректен"}
            )
        if profile.image is not None and not link_is_correct(profile.image):
            return JSONResponse(
                status_code=400,
                content={"reason": "Ссылка некорректна"}
            )
        if not email_is_correct(profile.email):
            return JSONResponse(
                status_code=400,
                content={"reason": "Почта некорректна"}
            )
        if database.get_countries_with_code(profile.countryCode) is None:
            return JSONResponse(
                status_code=400,
                content={"reason": "Код страны некорректен"}
            )
        if database.user_property_is_exists("login", profile.login) or database.user_property_is_exists("email", profile.email) \
                or (profile.phone is not None and database.user_property_is_exists("phone", profile.phone)):
            return JSONResponse(
                status_code=409,
                content={"reason": "Такие данные уже существуют"}
            )
        database.create_user(profile.login, profile.email, profile.password,
                                      profile.countryCode, profile.isPublic,
                             profile.phone if profile.phone is not None else "",
                             profile.image if profile.image is not None else "")
        output_profile = ProfileWithoutPassword(login=profile.login, email=profile.email,
                                                                    countryCode=profile.countryCode, isPublic=profile.isPublic,
                                                                    phone=profile.phone, image=profile.image)
        return JSONResponse(status_code=201, content={"profile":output_profile.dict(exclude_none=True)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/auth/sign-in')
async def sign_in(data: SignInData):
    try:
        user = database.get_user_by_propety("login", data.login)
        if user is None:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"reason": "Пользователь с указанным логином не найден"}
            )
        if not bcrypt.checkpw(data.password.encode(), str(user[2]).encode()):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"reason": "Пользователь с указанным паролем не найден"}
            )

        payload = {
            "login": data.login,
            "exp": datetime.now(tz=timezone.utc) + timedelta(hours=3)
        }

        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        database.add_token_to_whitelist(token)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"token": token}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/me/profile")
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    try:
        credentials_exception = JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"reason": "Пользователь с указанным токеном не найден"}
            )
        if not database.token_is_in_whitelist(token):
            return credentials_exception
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("login")
            if username is None:
                return credentials_exception
        except PyJWTError:
            return credentials_exception
        user = database.get_user_by_propety("login", username)
        if user is None:
            return credentials_exception
        return JSONResponse(jsonable_encoder(ProfileWithoutPassword(login=user[0], email=user[1],
                                                                        countryCode=user[3], isPublic=bool(user[4]),
                                                                        phone=user[5] if len(user[5]) > 0 else None,
                                                                    image=user[6] if len(user[6]) > 0 else None).dict(exclude_none=True)), status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/me/profile")
async def patch_current_user(token: Annotated[str, Depends(oauth2_scheme)], change_profile_list: ChangeProfileList):
    try:
        credentials_exception = JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"reason": "Пользователь с указанным токеном не найден"}
            )
        if not database.token_is_in_whitelist(token):
            return credentials_exception
        if change_profile_list.countryCode is None and change_profile_list.phone is None and change_profile_list.image is None \
            and change_profile_list.isPublic is None:
            return JSONResponse(
                status_code=400,
                content={"reason": "Данные пусты"}
            )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("login")
            if username is None:
                return credentials_exception
        except PyJWTError:
            return credentials_exception
        user = database.get_user_by_propety("login", username)
        if user is None:
            return credentials_exception
        if change_profile_list.phone is not None and not phone_is_correct(change_profile_list.phone):
            return JSONResponse(
                status_code=400,
                content={"reason": "Номер телефона некорректен"}
            )
        if change_profile_list.image is not None and not link_is_correct(change_profile_list.image):
            return JSONResponse(
                status_code=400,
                content={"reason": "Ссылка некорректна"}
            )
        if change_profile_list.phone is not None and database.user_property_is_exists("phone", change_profile_list.phone):
            return JSONResponse(
                status_code=409,
                content={"reason": "Такие данные уже существуют"}
            )
        if change_profile_list.countryCode is not None and database.get_countries_with_code(change_profile_list.countryCode) is None:
            return JSONResponse(
                status_code=400,
                content={"reason": "Код страны некорректен"}
            )
        database.update_user(username, change_profile_list)
        user = database.get_user_by_propety("login", username)
        return JSONResponse(jsonable_encoder(ProfileWithoutPassword(login=user[0], email=user[1],
                                                                        countryCode=user[3], isPublic=bool(user[4]),
                                                                        phone=user[5] if len(user[5]) > 0 else None,
                                                                    image=user[6] if len(user[6]) > 0 else None).dict(exclude_none=True)), status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/me/updatePassword")
async def update_password(token: Annotated[str, Depends(oauth2_scheme)], data: ChangePassword):
    try:
        if not password_is_correct(data.newPassword):
            return JSONResponse(
                status_code=400,
                content={"reason": "Новый пароль некорректен"}
            )
        if data.newPassword == data.oldPassword:
            return JSONResponse(
                status_code=403,
                content={"reason": "Новый пароль совпадает со старым"}
            )
        credentials_exception = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"reason": "Пользователь с указанным токеном не найден"}
        )
        if not database.token_is_in_whitelist(token):
            return credentials_exception
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("login")
            if username is None:
                return credentials_exception
        except PyJWTError:
            return credentials_exception
        user = database.get_user_by_propety("login", username)
        if user is None:
            return credentials_exception
        if not bcrypt.checkpw(data.oldPassword.encode(), str(user[2]).encode()):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"reason": "Пароль неверен"}
            )
        database.update_user_password(username, data.newPassword)
        database.remove_token_from_whitelist(token)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/profiles/{login}")
async def get_profile(token: Annotated[str, Depends(oauth2_scheme)], login: str):
    try:
        credentials_exception = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"reason": "Пользователь с указанным токеном не найден"}
        )
        if not database.token_is_in_whitelist(token):
            return credentials_exception
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("login")
            if username is None:
                return credentials_exception
        except PyJWTError:
            return credentials_exception
        user = database.get_user_by_propety("login", username)
        if user is None:
            return credentials_exception
        searched_profile = database.get_user_by_propety("login", login)
        exc_403 = JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"reason": "Профиль не может быть получен: либо пользователь с указанным логином не существует, либо у отправителя запроса нет доступа к запрашиваемому профилю"}
        )
        if searched_profile is None:
            return exc_403
        if searched_profile[4] or database.friend_is_in_friends(username, login):
            return JSONResponse(jsonable_encoder(ProfileWithoutPassword(login=searched_profile[0], email=searched_profile[1],
                                                                        countryCode=searched_profile[3], isPublic=bool(searched_profile[4]),
                                                                        phone=searched_profile[5] if len(searched_profile[5]) > 0 else None,
                                                                    image=searched_profile[6] if len(searched_profile[6]) > 0 else None).dict(exclude_none=True)), status_code=200)
        else:
            return exc_403
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/friends/add")
async def add_friend(token: Annotated[str, Depends(oauth2_scheme)], data: ChangeFriendData):
    try:
        credentials_exception = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"reason": "Пользователь с указанным токеном не найден"}
        )
        if not database.token_is_in_whitelist(token):
            return credentials_exception
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("login")
            if username is None:
                return credentials_exception
        except PyJWTError:
            return credentials_exception
        user = database.get_user_by_propety("login", username)
        if user is None:
            return credentials_exception
        if database.get_user_by_propety("login", data.login) is None:
            return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"reason": "Пользователь с указанным логином не найден"}
        )
        if username == data.login:
            return {"status" : "ok"}
        if database.friend_is_in_friends(username, data.login):
            return {"status": "in friends already"}
        database.add_friend(username, data.login)
        return {"status" : "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/friends/remove")
async def remove_friend(token: Annotated[str, Depends(oauth2_scheme)], data: ChangeFriendData):
    try:
        credentials_exception = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"reason": "Пользователь с указанным токеном не найден"}
        )
        if not database.token_is_in_whitelist(token):
            return credentials_exception
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("login")
            if username is None:
                return credentials_exception
        except PyJWTError:
            return credentials_exception
        user = database.get_user_by_propety("login", username)
        if user is None:
            return credentials_exception
        if not database.friend_is_in_friends(username, data.login):
            return {"status": "ok"}
        database.remove_friend(username, data.login)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/friends")
async def get_friends(token: Annotated[str, Depends(oauth2_scheme)], limit:int = 5, offset: int = 0):
    try:
        credentials_exception = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"reason": "Пользователь с указанным токеном не найден"}
        )
        if not database.token_is_in_whitelist(token):
            return credentials_exception
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("login")
            if username is None:
                return credentials_exception
        except PyJWTError:
            return credentials_exception
        user = database.get_user_by_propety("login", username)
        if user is None:
            return credentials_exception
        friends_data = database.get_friends(username)
        if friends_data is None:
            return []
        friends: [Friend] = []
        i = 0
        while i < len(friends_data):
            friends.append(Friend(login=friends_data[i + 1],addedAt=generate(datetime.strptime(friends_data[i], "%m/%d/%Y, %H:%M:%SZ").replace(tzinfo=pytz.utc), accept_naive=True)))
            i += 2
        return JSONResponse(jsonable_encoder(friends[int(offset): int(offset) + int(limit)]))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/posts/new")
async def create_post(token: Annotated[str, Depends(oauth2_scheme)], post: Post):
    try:
        if not validate_post(post):
            return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"reason": "Пост содержит некорректные данные"}
        )
        credentials_exception = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"reason": "Пользователь с указанным токеном не найден"}
        )
        if not database.token_is_in_whitelist(token):
            return credentials_exception
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("login")
            if username is None:
                return credentials_exception
        except PyJWTError:
            return credentials_exception
        user = database.get_user_by_propety("login", username)
        if user is None:
            return credentials_exception
        data = database.add_post(post, username)
        data.createdAt = generate(datetime.strptime(data.createdAt, "%m/%d/%Y, %H:%M:%SZ").replace(tzinfo=pytz.utc), accept_naive=True)
        return JSONResponse(jsonable_encoder(data))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/posts/{postId}")
async def get_post(token: Annotated[str, Depends(oauth2_scheme)], postId: str):
    try:
        credentials_exception = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"reason": "Пользователь с указанным токеном не найден"}
        )
        if not database.token_is_in_whitelist(token):
            return credentials_exception
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("login")
            if username is None:
                return credentials_exception
        except PyJWTError:
            return credentials_exception
        user = database.get_user_by_propety("login", username)
        if user is None:
            return credentials_exception
        if not database.post_is_existed(postId):
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"reason": "Пост либо недоступен, либо не существует"}
            )
        post = database.get_post(postId)
        post.createdAt = generate(datetime.strptime(post.createdAt, "%m/%d/%Y, %H:%M:%SZ").replace(tzinfo=pytz.utc),
                                  accept_naive=True)
        if database.get_user_by_propety("login", post.author)[4] or database.friend_is_in_friends(username, post.author) or username == post.author:
            return JSONResponse(jsonable_encoder(post))
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"reason": "Пост либо недоступен, либо не существует"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/posts/feed/my")
def get_my_posts(token: Annotated[str, Depends(oauth2_scheme)], limit: int = 5, offset: int = 0):
    try:
        credentials_exception = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"reason": "Пользователь с указанным токеном не найден"}
        )
        if not database.token_is_in_whitelist(token):
            return credentials_exception
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("login")
            if username is None:
                return credentials_exception
        except PyJWTError:
            return credentials_exception
        user = database.get_user_by_propety("login", username)
        if user is None:
            return credentials_exception
        posts = database.get_posts_by_login(username)
        if posts is None:
            return []
        for post in posts:
            post.createdAt = generate(datetime.strptime(post.createdAt, "%m/%d/%Y, %H:%M:%SZ").replace(tzinfo=pytz.utc),
                                  accept_naive=True)
        posts = posts[::-1]
        return JSONResponse(jsonable_encoder(posts[int(offset):int(offset) + int(limit)]))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/posts/feed/{login}")
def get_posts_by_login(token: Annotated[str, Depends(oauth2_scheme)], login: str, limit: int = 5, offset: int = 0):
    try:
        if login == "my":
            return get_my_posts(token, limit, offset)
        credentials_exception = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"reason": "Пользователь с указанным токеном не найден"}
        )
        if not database.token_is_in_whitelist(token):
            return credentials_exception
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("login")
            if username is None:
                return credentials_exception
        except PyJWTError:
            return credentials_exception
        user = database.get_user_by_propety("login", username)
        if user is None:
            return credentials_exception
        user = database.get_user_by_propety("login", login)
        if user is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"reason": "Такого пользователя не существует"}
            )
        posts = database.get_posts_by_login(login)
        if posts is None:
            return []
        for post in posts:
            post.createdAt = generate(datetime.strptime(post.createdAt, "%m/%d/%Y, %H:%M:%SZ").replace(tzinfo=pytz.utc),
                                  accept_naive=True)
        posts = posts[::-1]
        if database.get_user_by_propety("login", login)[4] or database.friend_is_in_friends(username, login) or username == login:
            return JSONResponse(jsonable_encoder(posts[int(offset):int(offset) + int(limit)]))
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"reason": "Посты недоступны"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/posts/{postId}/like")
def set_like(token: Annotated[str, Depends(oauth2_scheme)], postId: str):
    try:
        credentials_exception = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"reason": "Пользователь с указанным токеном не найден"}
        )
        if not database.token_is_in_whitelist(token):
            return credentials_exception
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("login")
            if username is None:
                return credentials_exception
        except PyJWTError:
            return credentials_exception
        user = database.get_user_by_propety("login", username)
        if user is None:
            return credentials_exception
        post = database.get_post(postId)
        if post is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"reason": "Пост либо недоступен, либо не существует"}
            )
        post.createdAt = generate(datetime.strptime(post.createdAt, "%m/%d/%Y, %H:%M:%SZ").replace(tzinfo=pytz.utc),
                                  accept_naive=True)
        if database.get_user_by_propety("login", post.author)[4] or database.friend_is_in_friends(username,
                                                                                                  post.author) or username == post.author:
            res = database.set_like(postId, username)
            if res == 1 or res == 2:
                post.likesCount += 1
                if res == 2:
                    post.dislikesCount -= 1
            return JSONResponse(jsonable_encoder(post))
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"reason": "Пост либо недоступен, либо не существует"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/posts/{postId}/dislike")
def set_dislike(token: Annotated[str, Depends(oauth2_scheme)], postId: str):
    try:
        credentials_exception = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"reason": "Пользователь с указанным токеном не найден"}
        )
        if not database.token_is_in_whitelist(token):
            return credentials_exception
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("login")
            if username is None:
                return credentials_exception
        except PyJWTError:
            return credentials_exception
        user = database.get_user_by_propety("login", username)
        if user is None:
            return credentials_exception
        post = database.get_post(postId)
        if post is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"reason": "Пост либо недоступен, либо не существует"}
            )
        post.createdAt = generate(datetime.strptime(post.createdAt, "%m/%d/%Y, %H:%M:%SZ").replace(tzinfo=pytz.utc),
                                  accept_naive=True)
        if database.get_user_by_propety("login", post.author)[4] or database.friend_is_in_friends(username,
                                                                                                  post.author) or username == post.author:
            res = database.set_dislike(postId, username)
            if res == 1 or res == 2:
                post.dislikesCount += 1
                if res == 2:
                    post.likesCount -= 1
            return JSONResponse(jsonable_encoder(post))
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"reason": "Пост либо недоступен, либо не существует"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

