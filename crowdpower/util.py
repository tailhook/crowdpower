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


def form(form_class):
    def decorator(fun):
        @web.decorator(fun)
        def form_processor(self, resolver, meth, *args, **kw):
            form = form_class(resolver.request.legacy_arguments)
            if kw and form.validate():
                return meth(**form.data)
            else:
                return dict(form=form)
        return form_processor
    return decorator
