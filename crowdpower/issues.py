import json

from zorro import web
from zorro import redis
from zorro.di import di
from zorro import zerogw
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

T_LEVEL = T.Enum(*LEVELS.keys())
T_TAG = T.Enum(*TAGS.keys())


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
        level=T_LEVEL,
        tags=T.List(T_TAG),
        reason=T.String,
        )

    def keys(self):
        yield 'issues:all'
        yield 'issues:l-{}'.format(self.level)
        for t in self.tags:
            yield 'issues:t-{}'.format(t)
        for t in self.tags:
            yield 'issues:l-{}:t-{}'.format(self.level, t)

    def tag_links(self):
        for t in self.tags:
            yield '/issues/tag/{}'.format(t), TAGS[t]

    def level_links(self):
        yield '/issues/lev/{}'.format(self.level), LEVELS[self.level]

    def save(self):
        self.redis.execute("SET", 'issue:{:d}'.format(self.id),
            self.dump_blob())


@has_dependencies
class Issues(web.Resource):

    jinja = dependency(jinja2.Environment, 'jinja')
    redis = dependency(redis.Redis, 'redis')
    output = dependency(zerogw.JSONWebsockOutput, "output")

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
        self.redis.pipeline([
            ('ZADD', 'rt:' + k, 0, siid)
            for k in issue.keys()])
        raise web.CompletionRedirect('/i/{:d}'.format(iid))

    @web.page
    def vote(self, issue:int, user:User):
        data = self.redis.execute('GET', 'issue:{:d}'.format(issue))
        iobj = Issue.load_blob(data)
        self.redis.execute('SADD',
            'votes:issue:{:d}'.format(iobj.id),
            user.uid)
        num = self.redis.execute('SCARD',
            'votes:issue:{:d}'.format(iobj.id))
        self.redis.pipeline([
            ('ZADD', 'rt:' + k, 0, iobj.id)
            for k in iobj.keys()])
        self.output._do_send((b'sendall',
            json.dumps(['vote', {
                'issue': issue,
                'votes': num,
                }]).encode('utf-8')))
        raise web.CompletionRedirect('/i/{:d}'.format(iobj.id))

    @template('issuelist.html')
    @web.page
    def all(self, start:int=0, stop:int=9):
        return self.redis_list('rt:issues:all', start=start, stop=stop)

    @template('issuelist.html')
    @web.page
    def lev(self, lev:T_LEVEL, start:int=0, stop:int=9):
        return self.redis_list('rt:issues:l-' + lev, start=start, stop=stop)

    @template('issuelist.html')
    @web.page
    def tag(self, tag:T_TAG, start:int=0, stop:int=9):
        return self.redis_list('rt:issues:t-' + tag, start=start, stop=stop)

    @template('issuelist.html')
    @web.page
    def ltag(self, level:T_LEVEL, tag:T_TAG, start:int=0, stop:int=9):
        return self.redis_list('rt:issues:l-{}:t-{}'.format(level, tag),
            start=start, stop=stop)

    def redis_list(self, key, *, start=0, stop=9):
        ids = self.redis.execute('ZREVRANGE', key, start, stop)
        ids = list(map(int, ids))
        pipeline = []
        for i in ids:
            pipeline.append(('GET', 'issue:{:d}'.format(i)))
            pipeline.append(('SCARD', 'votes:issue:{:d}'.format(i)))
        issues = []
        if pipeline:
            for data, vt in zip(*[iter(self.redis.pipeline(pipeline))]*2):
                i = Issue.load_blob(data)
                i.votes = int(vt)
                issues.append(i)
        return {
            'issues': issues,
            }


@has_dependencies
class ShowIssue(web.Resource):

    jinja = dependency(jinja2.Environment, 'jinja')
    redis = dependency(redis.Redis, 'redis')

    @template('issue.html')
    @web.page
    def i(self, num: int):
        data = self.redis.execute('GET', 'issue:{:d}'.format(num))
        issue = Issue.load_blob(data)
        user = User.get(di(self), issue.uid)
        return {
            'issue': issue,
            'user': user,
            }
