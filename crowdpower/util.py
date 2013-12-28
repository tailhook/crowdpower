from zorro import web

def template(name):
    def decorator(fun):
        @web.postprocessor(fun)
        def wrapper(self, resolver, data):
            return ('200 OK',
                    'Content-Type\0text/html; charset=utf-8\0',
                    self.jinja.get_template(name).render(data))
        return wrapper
    return decorator
