from zorro.di import has_dependencies, dependency
from zorro import web
import wtforms
import jinja2
from wtforms import validators as val

from .util import form
from .util import template

_ = lambda _: _


class RegisterForm(wtforms.Form):
    firstname = wtforms.TextField(_('Ім’я'),
        validators=[val.Required(), val.Length(min=3, max=24)])
    middlename = wtforms.TextField(_('По-батькові'),
        validators=[val.Required(), val.Length(min=3, max=24)])
    lastname = wtforms.TextField(_('Прізвище'),
        validators=[val.Required(), val.Length(min=3, max=24)])
    birthyear = wtforms.IntegerField(_('Рік народження'),
        validators=[val.Required()])
    email = wtforms.TextField(_('E-mail'),
        validators=[val.Required(), val.Email()])
    phone = wtforms.TextField(_('Моб. телефон'),
        validators=[val.Required()])
    password = wtforms.PasswordField(_('Пароль'),
        validators=[val.Required()])
    cpassword = wtforms.PasswordField(_('Підтвердження паролю'),
        validators=[val.Required(), val.EqualTo('password')])


@has_dependencies
class Register(web.Resource):

    jinja = dependency(jinja2.Environment, 'jinja')

    @web.page
    @template('register.html')
    @form(RegisterForm)
    def index(self, form):
        return {}
