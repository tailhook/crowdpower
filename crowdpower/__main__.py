import jinja2
from zorro import Hub
from zorro import zmq
from zorro import web
from zorro.di import DependencyInjector, dependency, has_dependencies
from zorro import redis

from .util import template
from .register import Register


@has_dependencies
class About(web.Resource):

    jinja = dependency(jinja2.Environment, 'jinja')

    @web.page
    @template('index.html')
    def index(self):
        return {}


class Request(web.Request):

    def __init__(self, uri, cookie, content_type, body):
        self.uri = uri
        self.cookie = cookie
        self.content_type = content_type
        self.body = body


def main():

    inj = DependencyInjector()
    inj['jinja'] = jinja2.Environment(
        loader=jinja2.PackageLoader(__name__, 'templates'))
    inj['redis'] = redis.Redis(
        unixsock='run/redis/redis.sock')

    site = web.Site(
        request_class=Request,
        resources=[
            inj.inject(About()),
            inj.inject(Register()),
        ])
    sock = zmq.rep_socket(site)
    sock.dict_configure({
        'connect': 'ipc://./run/http.sock'
        })


if __name__ == '__main__':
    hub = Hub()
    hub.run(main)
