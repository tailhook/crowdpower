from zorro.di import has_dependencies, dependency
from zorro import web
from zorro import redis
from http.cookies import SimpleCookie as Cookie
import hashlib
import binascii
import wtforms
import jinja2
import uuid
import os
from wtforms import validators as val

from .util import form, FormError
from .util import template
from .user import User

_ = lambda _: _


@has_dependencies
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

    redis = dependency(redis.Redis, 'redis')

    def validate_phone(self, field):
        uid = self.redis.execute('HGET', 'phones', field.data)
        if uid is not None:
            raise ValueError(_("Номер телефону вже використовується"))

    def validate_email(self, field):
        uid = self.redis.execute('HGET', 'emails', field.data)
        if uid is not None:
            raise ValueError(_("E-mail вже використовується"))


class LoginForm(wtforms.Form):
    email = wtforms.TextField(_('E-mail'),
        validators=[val.Required(), val.Email()])
    password = wtforms.PasswordField(_('Пароль'),
        validators=[val.Required()])


@has_dependencies
class Register(web.Resource):

    jinja = dependency(jinja2.Environment, 'jinja')
    redis = dependency(redis.Redis, 'redis')

    @template('register.html')
    @form(RegisterForm)
    @web.page
    def register(self,
            firstname, middlename, lastname, birthyear,
            email, phone, password):

        salt = os.urandom(8)
        hh = hashlib.sha256(salt + password.encode('ascii'))
        pw = binascii.b2a_base64(salt) + b':' + hh.hexdigest().encode('ascii')

        uid = int(self.redis.execute('INCR', 'userid'))
        u = User(
            uid=uid,
            firstname=firstname,
            middlename=middlename,
            lastname=lastname,
            birthyear=birthyear,
            email=email,
            phone=phone)
        self.redis.execute('SET', 'user:{:d}'.format(uid), u.dump_blob())
        self.redis.execute('HSET', 'emails', email, str(uid))
        self.redis.execute('HSET', 'phones', phone, str(uid))
        self.redis.execute('HSET', 'passwords', email, pw)

        self.authorize(uid)

    def authorize(self, uid):
        sess = str(uuid.uuid4())
        self.redis.execute('SETEX',
            'sess:{}'.format(sess), str(86400), str(uid))
        cookie = Cookie()
        cookie['sida'] = sess
        cookie['sida']['max-age'] = 86400
        cookie['sidb'] = sess
        raise web.CompletionRedirect('/', cookie=cookie)

    @template('login.html')
    @form(LoginForm)
    @web.page
    def login(self, email, password):
        val = self.redis.execute('HGET', 'passwords', email)
        if val:
            try:
                salt, hash = val.decode('ascii').split(':')
                mhash = binascii.a2b_base64(salt) + password.encode('ascii')
                hh = hashlib.sha256(mhash)
                if hash == hh.hexdigest():
                    uid = int(self.redis.execute('HGET', 'emails', email))
                    self.authorize(uid)
            except ValueError:
                pass
        raise FormError('email', _('Невірний e-mail або пароль'))

    @web.page
    def logout(self, req:web.Request):
        sid = req.cookies.get('sida')
        if sid:
            self.redis.execute('DEL', 'sess:' + sid)
        sid = req.cookies.get('sidb')
        if sid:
            self.redis.execute('DEL', 'sess:' + sid)
        cookie = Cookie()
        cookie['sida'] = ''
        cookie['sidb'] = ''
        raise web.CompletionRedirect('/', cookie=cookie)

    @web.page
    def uid(self, user: User):
        return str(user.uid)
