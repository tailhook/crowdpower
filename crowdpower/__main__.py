from zorro import Hub
from zorro import zmq
from zorro import web


class About(web.Resource):

    @web.page
    def index(self):
        return "Hello World!"


class Request(web.Request):

    def __init__(self, uri, cookie, content_type, body):
        self.uri = uri
        self.cookie = cookie
        self.content_type = content_type
        self.body = body


def main():

    site = web.Site(
        request_class=Request,
        resources=[
            About(),
        ])
    sock = zmq.rep_socket(site)
    sock.dict_configure({
        'connect': 'ipc://./run/http.sock'
        })


if __name__ == '__main__':
    hub = Hub()
    hub.run(main)
