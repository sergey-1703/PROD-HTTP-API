from typing import Dict, Any, Optional

from pydantic import BaseModel


class Country(BaseModel):
    name: str
    alpha2: str
    alpha3: str
    region: str


class Profile(BaseModel):
    login: str
    email: str
    password: str
    countryCode: str
    isPublic: bool
    phone: Optional[str] = None
    image: Optional[str] = None


class ChangeProfileList(BaseModel):
    countryCode: Optional[str] = None
    isPublic: Optional[bool] = None
    phone: Optional[str] = None
    image: Optional[str] = None


class SignInData(BaseModel):
    login: str
    password: str


class ChangeFriendData(BaseModel):
    login: str


class Friend(BaseModel):
    login: str
    addedAt: str


class ChangePassword(BaseModel):
    oldPassword: str
    newPassword: str


class Post(BaseModel):
    content: str
    tags: list[str]


class PostInfo(BaseModel):
    id: str
    content: str
    author: str
    tags: list[str]
    createdAt: str
    likesCount: int
    dislikesCount: int


class ProfileWithoutPassword(BaseModel):
    login: str
    email: str
    countryCode: str
    isPublic: bool
    phone: Optional[str] = None
    image: Optional[str] = None

    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        kwargs.pop('exclude_none', None)
        return super().dict(*args, exclude_none=True, **kwargs)




