import bcrypt


def hash_password(password: str):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(f"{password}".encode(), salt)

