import re
from models import Post


def login_is_correct(login: str):
    return re.match(r"[a-zA-Z0-9-]+", login) and len(login) <= 30


def email_is_correct(email: str):
    return re.match(r"([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+",email) and 1<=len(email)<=50


def password_is_correct(password: str):
    return re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{6,}$", password) and len(password) <= 100


def phone_is_correct(phone: str):
    return re.match(r"\+[\d]+", phone) and len(phone) <= 20


def link_is_correct(link: str):
    return 1 <= len(link) <= 200


def validate_post(post: Post):
    return len(post.content) <= 1000 and all(len(x) <= 20 for x in post.tags)
