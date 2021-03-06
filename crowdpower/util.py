from zorro import web
from zorro.di import di

from .user import User


class FormError(Exception):

    def __init__(self, field, text):
        self.field = field
        self.text = text


def template(name):
    def decorator(fun):
        @web.postprocessor(fun)
        def wrapper(self, resolver, data):
            try:
                u = User.create(resolver)
            except web.CompletionRedirect:
                u = None
            adata = {
                'user': u,
                'uri': resolver.request.parsed_uri.path,
                }
            adata.update(data)
            return ('200 OK',
                    'Content-Type\0text/html; charset=utf-8\0',
                    self.jinja.get_template(name).render(adata))
        return wrapper
    return decorator


def form(form_class):
    def decorator(fun):
        @web.decorator(fun)
        def form_processor(self, resolver, meth, *args, **kw):
            form = form_class(resolver.request.legacy_arguments)
            di(self).inject(form)
            if kw and form.validate():
                try:
                    return meth(**form.data)
                except FormError as e:
                    getattr(form, e.field).errors.append(e.text)
                    return dict(form=form)
            else:
                return dict(form=form)
        return form_processor
    return decorator

def save_form(form_class, getter):
    def decorator(fun):
        @web.decorator(fun)
        def form_processor(self, resolver, meth, objid, *args, **kw):
            obj = getter(self, objid)
            form = form_class(resolver.request.legacy_arguments, obj=obj)
            if kw and form.validate():
                try:
                    return meth(obj, **form.data)
                except FormError as e:
                    getattr(form, e.field).errors.append(e.text)
                    return dict(form=form)
            else:
                return dict(form=form)
        return form_processor
    return decorator
