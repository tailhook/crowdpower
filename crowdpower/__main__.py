import jinja2
from zorro import Hub
from zorro import zmq
from zorro import web
from zorro.di import DependencyInjector, dependency, has_dependencies
from zorro import redis
from zorro import zerogw

from .util import template
from .register import Register
from .issues import Issues, ShowIssue


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

    sock = zmq.pub_socket()
    sock.dict_configure({'connect': 'ipc://./run/sub.sock'})
    output = zerogw.JSONWebsockOutput(sock)
    inj['output'] = output

    sock = zmq.pull_socket(inj.inject(web.Websockets(
        resources=[],
        output=output,
        )))
    sock.dict_configure({'connect': 'ipc://./run/fw.sock'})

    site = web.Site(
        request_class=Request,
        resources=[
            inj.inject(About()),
            inj.inject(Register()),
            web.DictResource(
                issues=inj.inject(Issues()),
                ),
            inj.inject(ShowIssue()),
        ])
    sock = zmq.rep_socket(site)
    sock.dict_configure({
        'connect': 'ipc://./run/http.sock'
        })



if __name__ == '__main__':
    hub = Hub()
    hub.run(main)
