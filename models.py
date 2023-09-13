from peewee import *
import datetime
from flask_login import UserMixin


db = PostgresqlDatabase(
    'event',
    host = 'localhost',
    port = '5432',
    user = 'ernaz',
    password = 'root'
)
db.connect()


class BaseModel(Model):
    class Meta:
        database = db


class Users(UserMixin, BaseModel):
    username = CharField(max_length=255, null=False, unique=True)
    age = IntegerField()
    email = CharField(max_length=255, null=False, unique=True)
    password = CharField(max_length=255, null=False)
    avatar = BlobField(null=True)


class Friendship(BaseModel):
    user = ForeignKeyField(Users, backref='friends')
    friend = ForeignKeyField(Users, backref='users')


class Occurrence(BaseModel):
    author = ForeignKeyField(Users, on_delete='CASCADE')
    title = CharField(max_length=255, null=False)
    content = TextField()
    created_date = DateTimeField(default=datetime.datetime.now)
    planned_date = DateTimeField()
    post_image = BlobField(null=True)
    public = BooleanField(default=False)


# db.create_tables([Friendship])