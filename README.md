# PROD HTTP API

REST API социальной сети, разработанное в рамках **2-го этапа олимпиады PROD 2024**.

Проект реализует базовый backend социальной платформы: регистрацию и авторизацию пользователей, управление профилем, систему друзей, публикацию постов, ленту, а также лайки и дизлайки.

## Возможности

- регистрация пользователей;
- авторизация по JWT;
- хранение паролей в виде bcrypt-хешей;
- получение и редактирование собственного профиля;
- публичные и приватные профили;
- просмотр профилей других пользователей с учетом настроек приватности;
- добавление и удаление друзей;
- получение списка друзей с пагинацией;
- создание и получение постов;
- персональная лента публикаций;
- просмотр публикаций других пользователей с учетом приватности;
- лайки и дизлайки;
- получение списка стран и фильтрация по регионам;
- автоматическая Swagger/OpenAPI-документация FastAPI;
- запуск в Docker-контейнере.

## Стек

- **Python 3.12**
- **FastAPI**
- **Uvicorn**
- **PostgreSQL**
- **psycopg2**
- **Pydantic**
- **JWT / PyJWT**
- **bcrypt**
- **Docker**

## Структура проекта

```text
PROD-HTTP-API/
├── source/
│   ├── app.py            # FastAPI-приложение и HTTP-эндпоинты
│   ├── database.py       # Работа с PostgreSQL
│   ├── models.py         # Pydantic-модели запросов и ответов
│   ├── validation.py     # Валидация пользовательских данных
│   ├── passwordtools.py  # Хеширование паролей через bcrypt
│   ├── config.py         # Загрузка конфигурации из переменных окружения
│   └── config.ini
├── Dockerfile
├── requirements.txt
├── .dockerignore
└── .gitignore
```

## API

### Системные методы

| Метод | Endpoint | Описание |
|---|---|---|
| `GET` | `/api/ping` | Проверка доступности API |
| `GET` | `/api/countries` | Получение списка стран; поддерживается фильтрация по регионам |
| `GET` | `/api/countries/{alpha2}` | Получение страны по ISO alpha-2 коду |

### Авторизация

| Метод | Endpoint | Описание |
|---|---|---|
| `POST` | `/api/auth/register` | Регистрация пользователя |
| `POST` | `/api/auth/sign-in` | Вход и получение JWT-токена |

JWT создается после успешного входа и используется в защищенных методах через заголовок:

```http
Authorization: Bearer <token>
```

Срок действия токена в текущей реализации — **3 часа**. Активные токены дополнительно хранятся в whitelist в PostgreSQL.

### Профиль

| Метод | Endpoint | Описание |
|---|---|---|
| `GET` | `/api/me/profile` | Получить собственный профиль |
| `PATCH` | `/api/me/profile` | Изменить настройки профиля |
| `POST` | `/api/me/updatePassword` | Изменить пароль |
| `GET` | `/api/profiles/{login}` | Получить профиль другого пользователя |

Профиль содержит:

```json
{
  "login": "user",
  "email": "user@example.com",
  "countryCode": "RU",
  "isPublic": true,
  "phone": "+79999999999",
  "image": "https://example.com/avatar.png"
}
```

Поля `phone` и `image` являются необязательными.

Для приватного профиля доступ ограничивается системой друзей.

### Друзья

| Метод | Endpoint | Описание |
|---|---|---|
| `POST` | `/api/friends/add` | Добавить пользователя в друзья |
| `POST` | `/api/friends/remove` | Удалить пользователя из друзей |
| `GET` | `/api/friends` | Получить список друзей |

Для списка друзей доступны параметры:

```text
limit
offset
```

По умолчанию `limit=5`, `offset=0`.

### Посты

| Метод | Endpoint | Описание |
|---|---|---|
| `POST` | `/api/posts/new` | Создать пост |
| `GET` | `/api/posts/{postId}` | Получить пост по ID |
| `GET` | `/api/posts/feed/my` | Получить собственные публикации |
| `GET` | `/api/posts/feed/{login}` | Получить публикации пользователя |
| `POST` | `/api/posts/{postId}/like` | Поставить лайк |
| `POST` | `/api/posts/{postId}/dislike` | Поставить дизлайк |

Пример создания поста:

```json
{
  "content": "Hello, PROD!",
  "tags": [
    "python",
    "fastapi"
  ]
}
```

Ответ содержит ID публикации, автора, дату создания и счетчики реакций:

```json
{
  "id": "1",
  "content": "Hello, PROD!",
  "author": "user",
  "tags": [
    "python",
    "fastapi"
  ],
  "createdAt": "2024-01-01T12:00:00Z",
  "likesCount": 0,
  "dislikesCount": 0
}
```

## Валидация

В API реализована базовая проверка входных данных:

- логин — латинские буквы, цифры и `-`, до 30 символов;
- email — до 50 символов;
- пароль — от 6 до 100 символов, минимум одна строчная буква, одна заглавная буква и одна цифра;
- телефон — формат с `+`, до 20 символов;
- текст поста — до 1000 символов;
- каждый тег — до 20 символов.

Пароли перед записью в базу хешируются с помощью **bcrypt**.

## База данных

Приложение работает с PostgreSQL через `psycopg2`.

При запуске автоматически создаются таблицы:

- `profiles` — пользователи и список друзей;
- `tokenswhitelist` — активные JWT-токены;
- `posts` — публикации, лайки и дизлайки.

Также API использует таблицу `countries`. Она должна быть создана и заполнена в базе данных заранее.

Подключение задается переменной окружения:

```env
POSTGRES_CONN=postgresql://username:password@localhost:5432/database
```

## Локальный запуск

### 1. Клонировать репозиторий

```bash
git clone https://github.com/sergey-1703/PROD-HTTP-API.git
cd PROD-HTTP-API
```

### 2. Создать виртуальное окружение

```bash
python -m venv .venv
```

Linux / macOS:

```bash
source .venv/bin/activate
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Настроить PostgreSQL

Задать строку подключения:

Linux / macOS:

```bash
export POSTGRES_CONN="postgresql://username:password@localhost:5432/database"
```

Windows PowerShell:

```powershell
$env:POSTGRES_CONN="postgresql://username:password@localhost:5432/database"
```

### 5. Запустить API

```bash
cd source
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

После запуска API будет доступно по адресу:

```text
http://localhost:8080
```

Swagger UI:

```text
http://localhost:8080/docs
```

ReDoc:

```text
http://localhost:8080/redoc
```

## Docker

Собрать образ:

```bash
docker build -t prod-http-api .
```

Запустить контейнер:

```bash
docker run --rm \
  -p 8080:8080 \
  -e POSTGRES_CONN="postgresql://username:password@host:5432/database" \
  prod-http-api
```

Приложение внутри контейнера запускается через Uvicorn на порту `8080`.

## Особенности реализации

- API построено на FastAPI и использует Pydantic-модели для структуры входных и выходных данных.
- Авторизация реализована через JWT с алгоритмом `HS256`.
- Для дополнительной проверки сессии JWT должен присутствовать в whitelist базы данных.
- После изменения пароля текущий токен удаляется из whitelist.
- Доступ к приватным профилям и публикациям зависит от наличия пользователя в списке друзей.
- Лайк и дизлайк взаимоисключающие: смена реакции удаляет предыдущую.
- Пагинация лент и списка друзей реализована через `limit` и `offset`.

## Назначение проекта

Проект демонстрирует реализацию backend-приложения с REST API, авторизацией, PostgreSQL, валидацией данных и Docker-контейнеризацией.

Репозиторий создан как решение задания второго этапа олимпиады **PROD 2024**.
