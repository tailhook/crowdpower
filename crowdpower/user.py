from zorro import redis
from zorro.di import has_dependencies, dependency
import trafaret as T
from zorro import web
from zorro.di import di

from .tobject import TObject


@has_dependencies
class User(TObject, web.Sticker):

    redis = dependency(redis.Redis, 'redis')

    contract = T.Dict(
        uid=T.Int,
        firstname=T.String,
        middlename=T.String,
        lastname=T.String,
        birthyear=T.Int,
        email=T.String,
        phone=T.String,
        )


    @classmethod
    def create(cls, resolver):
        req = resolver.request
        sid = req.cookies.get('sidb')
        if sid is None:
            sid = req.cookies.get('sida')
        if sid is None:
            raise web.CompletionRedirect('/login')
        inj = di(resolver.resource)
        redis = inj['redis']
        uid = redis.execute("GET", 'sess:' + sid)
        if uid is None:
            raise web.CompletionRedirect('/login')
        uid = int(uid)
        data = inj['redis'].execute("GET", 'user:{:d}'.format(uid))
        user = cls.load_blob(data)
        assert user.uid == uid
        return user

    def save(self):
        self.redis.execute("SET", 'user:{:d}'.format(self.uid),
            self.dump_blob())
