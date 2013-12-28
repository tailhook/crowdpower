from zorro import web
from zorro import redis
from zorro.di import di
import wtforms
import jinja2
import yaml
from itertools import product
from wtforms import validators as val
from zorro.di import dependency, has_dependencies
from collections import OrderedDict
import trafaret as T

from .util import template, form
from .user import User
from .tobject import TObject

_ = lambda _: _


with open('levels.yaml', 'rb') as f:
    LEVELS = OrderedDict(
        (k, v) for pair in yaml.load(f)
               for k, v in pair.items())

with open('tags.yaml', 'rb') as f:
    TAGS = yaml.load(f)


class IssueForm(wtforms.Form):

    brief = wtforms.TextAreaField(_('Короткий опис'),
        validators=[val.Required(), val.Length(min=24, max=120)])
    level = wtforms.SelectField(_('Рівень'), choices=LEVELS.items())
    tags = wtforms.SelectMultipleField(_('Теги'), choices=TAGS.items())
    reason = wtforms.TextAreaField(_('Чому ви подаєте петицію?'),
        validators=[val.Required()])


@has_dependencies
class Issue(TObject):

    redis = dependency(redis.Redis, 'redis')
    contract = T.Dict(
        id=T.Int,
        uid=T.Int,
        brief=T.String,
        level=T.Enum(*LEVELS.keys()),
        tags=T.List(T.Enum(*TAGS.keys())),
        reason=T.String,
        )

    def keys(self):
        yield 'issues:all'
        yield 'issues:l-{}'.format(self.level)
        for t in self.tags:
            yield 'issues:t-{}'.format(t)
        for t in self.tags:
            yield 'issues:l-{}:t-{}'.format(self.level, t)

    def save(self):
        self.redis.execute("SET", 'issue:{:d}'.format(self.id),
            self.dump_blob())


@has_dependencies
class Issues(web.Resource):

    jinja = dependency(jinja2.Environment, 'jinja')
    redis = dependency(redis.Redis, 'redis')

    @template('newissue.html')
    @form(IssueForm)
    @web.page
    def new(self, user:User, brief, level, tags, reason):
        iid = int(self.redis.execute('INCR', 'issueid'))
        siid = str(iid)
        issue = di(self).inject(Issue(
            id=iid,
            uid=user.uid,
            brief=brief,
            level=level,
            tags=tags,
            reason=reason,
            ))
        issue.save()
        futures = []
        for k in issue.keys():
            futures.append(self.redis.future('ZADD', 'votes:' + k, 0, siid))
        for f in futures:
            f.get()
        raise web.CompletionRedirect('/i/{:d}'.format(iid))
