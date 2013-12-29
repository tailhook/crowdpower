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

from .util import template, form, save_form
from .user import User, OptionalUser
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
T_STATE = T.Enum(
    'draft', 'active',
    'ready', 'sent',
    'responded', 'timedout',
    'preparing', 'acting',
    'closed')


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
    contract = T.Dict({
        'id': T.Int,
        'uid': T.Int,
        'brief': T.String,
        'level': T_LEVEL,
        'tags': T.List(T_TAG),
        'reason': T.String,
        T.Key('state', default='active'): T_STATE,
        T.Key('response', optional=True): T.String,
        T.Key('action', optional=True): T.String,
        })

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
            for k in issue.keys()]
            + [('LPUSH', 'rc:issues', siid),
               ('LTRIM', '0', '10')])
        raise web.CompletionRedirect('/i/{:d}'.format(iid))


    def get_issue(self, issue):
        data = self.redis.execute('GET', 'issue:{:d}'.format(int(issue)))
        iobj = di(self).inject(Issue.load_blob(data))
        return iobj

    @template('newissue.html')
    @save_form(IssueForm, get_issue)
    @web.page
    def edit(self, user:User, iobj, brief, level, tags, reason):
        if iobj.uid != user.uid and not user.admin:
            raise web.CompletionRedirect('/login')
        oldkeys = set(iobj.keys())
        iobj.brief = brief
        iobj.level = level
        iobj.tags = tags
        iobj.reason = reason
        newkeys = set(iobj.keys())
        iobj.save()
        kdiff = [('ZADD', 'rt:' + k, 0, iobj.id)
                 for k in newkeys - oldkeys
                ] + [('ZREM', 'rt:' + k, 0, iobj.id)
                 for k in oldkeys - newkeys]
        if kdiff:
            self.redis.pipeline(kdiff)
        raise web.CompletionRedirect('/i/{:d}'.format(iobj.id))

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
            ('ZADD', 'rt:' + k, num, iobj.id)
            for k in iobj.keys()])
        self.output._do_send((b'sendall',
            json.dumps(['vote', {
                'issue': issue,
                'votes': num,
                }]).encode('utf-8')))
        raise web.CompletionRedirect('/i/{:d}'.format(iobj.id))

    @template('issuelist.html')
    @web.page
    def all(self, *, start:int=0, stop:int=9, user:OptionalUser=None):
        return self.redis_list('rt:issues:all',
            start=start, stop=stop, user=user)

    @template('issuelist.html')
    @web.page
    def lev(self, lev:T_LEVEL, *, start:int=0, stop:int=9, user:OptionalUser):
        return self.redis_list('rt:issues:l-' + lev,
            start=start, stop=stop, user=user)

    @template('issuelist.html')
    @web.page
    def tag(self, tag:T_TAG, *, start:int=0, stop:int=9, user:OptionalUser):
        return self.redis_list('rt:issues:t-' + tag,
            start=start, stop=stop, user=user)

    @template('issuelist.html')
    @web.page
    def ltag(self, level:T_LEVEL, tag:T_TAG,
        *, start:int=0, stop:int=9, user:OptionalUser):
        return self.redis_list('rt:issues:l-{}:t-{}'.format(level, tag),
            start=start, stop=stop, user=user)

    @web.page
    @template('home.html')
    def index(self, user:OptionalUser):
        rated = self.redis.execute('ZREVRANGE', 'rt:issues:all', 0, 3)
        recent = self.redis.execute('LRANGE', 'rc:issues', 0, 3)
        return {
            'rated_issues': self.fetch_list(list(map(int, rated)), user),
            'recent_issues': self.fetch_list(list(map(int, recent)), user),
            }

    def redis_list(self, key, *, start=0, stop=9, user):
        ids = self.redis.execute('ZREVRANGE', key, start, stop)
        return {
            'issues': self.fetch_list(list(map(int, ids)), user),
            }

    def fetch_list(self, ids, user):
        pipeline = []
        for i in ids:
            pipeline.append(('GET', 'issue:{:d}'.format(i)))
            pipeline.append(('SCARD', 'votes:issue:{:d}'.format(i)))
            pipeline.append(('SISMEMBER',
                'votes:issue:{:d}'.format(i), str(user.uid)))
        issues = []
        if pipeline:
            for data, vt, uv in zip(*[iter(self.redis.pipeline(pipeline))]*3):
                i = Issue.load_blob(data)
                i.votes = int(vt)
                i.user_voted = bool(int(uv))
                issues.append(i)
        return issues


@has_dependencies
class ShowIssue(web.Resource):

    jinja = dependency(jinja2.Environment, 'jinja')
    redis = dependency(redis.Redis, 'redis')

    def __zorro_di_done__(self):
        self.issues = di(self).inject(Issues())

    @template('home.html')
    @web.page
    def index(self, user:User):
        return self.issues.index(user=user)

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
