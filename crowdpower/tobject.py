import abc

import msgpack
import trafaret as T


class TObjectMeta(abc.ABCMeta):

    def __init__(self, name, bases, dic):
        contr = dic.get('contract')
        if contr is not None:
            contr.append(self)


class TObject(metaclass=TObjectMeta):

    contract = None  # override in subclass

    def __init__(self, data=None, **kw):
        if data is None:
            data = self.contract.check_and_return(kw)
        # else:  # we assume that data is checked by contract
        self.__dict__.update(data)

    @classmethod
    def load(cls, data):
        return cls.contract.check(data)

    def dump(self):
        res = {}
        for k in self.contract.keys:
            try:
                val = getattr(self, k.to_name or k.name)
            except AttributeError:
                if k.optional:
                    continue
                else:
                    raise RuntimeError("{!r} object has not attribte {!r}"
                        .format(self, k.to_name or k.name))
            if isinstance(val, TObject):
                val = val.dump()
            elif isinstance(k.trafaret, (T.List, T.Tuple)) \
                and all(isinstance(v, TObject) for v in val):
                if isinstance(k.trafaret, T.List):
                    val = list(i.dump() for i in val)
                else:
                    val = tuple(i.dump() for i in val)
            elif isinstance(k.trafaret, (T.Dict, T.Mapping)) \
                and all(isinstance(v, TObject) for v in val.values()):
                val = {k: v.dump() for k, v in val.items()}
                # TODO: maybe also check key values
            res[k.name] = val
        return res

    def copy(self):
        return self.__class__(self.dump())  # TODO(pc) may be faster way?

    @classmethod
    def load_blob(cls, data):
        return cls.load(msgpack.loads(data, encoding='utf-8', use_list=True))

    def dump_blob(self):
        data = self.dump()
        self.contract.check(data)
        return msgpack.dumps(data, encoding='utf-8')
