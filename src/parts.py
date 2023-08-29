import pickle
import time

from mmcore.services.redis.stream import StreamConnector


class Column:
    reference: bool = False

    def __init__(self, reference=False, dtype: type = int, default=None):
        super().__init__()
        self.data = dict()
        self.reference = reference
        self.dtype = dtype
        self.default = default
        if default is not None:
            self.default = self.dtype(default)
            assert type(self.dtype(self.default)) == self.dtype
    def set_data(self, v):
        self.data=v
    def set(self, part, val):
        if self.reference:
            self.data[part.ixs()] = val
        else:
            self.data[part._j] = val

    def get(self, part):
        if self.reference:
            v = self.data.get(part.ixs())
            if v is None:
                if self.default:
                    return self.dtype(self.default)
                return self.dtype()

            return v

        else:

            v = self.data.get(part._j)
            if v is None:
                if self.default:
                    return self.dtype(self.default)

                return self.dtype()

            return v

    def dumps(self):
        return pickle.dumps(self)
class Db:
    def __init__(self, index_map,  **columns):
        super().__init__()
        self.cols = columns
        self.index_map = index_map

    def dumps(self):

        pickle.dumps(self)

class Part:
    """
    >>> ixs_map=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 2, 12, 6, 1, 22, 16, 21, 2, 5, 19, 0, 19]
    >>> cols_db = Db(ixs_map,
    ...     tag=Column(reference=True, dtype=int),
    ...     mount=Column(reference=False, dtype=bool),
    ...     type=Column(reference=True, dtype=str, default="A")
    ... )

    >>> oo = Part(30,  cols_db , type="A", mount=False, tag=10)
    >>> *tv, = oo.tweens()
    >>> tv[0].set("mount", True)
    >>> [(k, [tvv.get(k) for tvv in oo.tweens()]) for k in oo.keys()]
[('tag', [10, 10]), ('mount', [True, False]), ('type', ['A', 'A'])]
    >>> oo._j=31
    >>> [(k, [tvv.get(k) for tvv in oo.tweens()]) for k in oo.keys()]
[('tag', [0, 0, 0]),
 ('mount', [False, False, False]),
 ('type', ['A', 'A', 'A'])]

    >>> list(oo.tweens())[1].set("mount",True)
    >>> [(k, [tvv.get(k) for tvv in oo.tweens()]) for k in oo.keys()]
[('tag', [0, 0, 0]),
 ('mount', [False, True, False]),
 ('type', ['A', 'A', 'A'])]

    >>> list(oo.tweens())[2].set("tag",10)
    >>> [(k, [tvv.get(k) for tvv in oo.tweens()]) for k in oo.keys()]
[('tag', [10, 10, 10]),
 ('mount', [False, True, False]),
 ('type', ['A', 'A', 'A'])]


    """

    def __init__(self, j, db, **kwargs):
        super().__init__()
        self._j = j

        self.db = db
        for k in self.keys():
            v = kwargs.get(k)
            if v is not None:
                self.set(k, v)

    def ixs(self):
        return self.db.index_map[self._j]

    def get(self, k):
        return self.db.cols[k].get(self)

    def set(self, k, v):
        self.db.cols[k].set(self, v)

    def keys(self):
        return self.db.cols.keys()

    def tweens(self):
        for jxx, ixx in enumerate(self.db.index_map):
            if ixx == self.ixs():
                yield Part(jxx, self.db)

    def __eq__(self, other):
        return self.ixs() == other.ixs() and self.db.index_map is other.db.index_map


#db = Db([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 2, 12, 6, 1, 22, 16, 21, 2, 5, 19, 0, 19],
#    tag=Column(reference=True, dtype=int),
#    mount=Column(reference=False, dtype=bool),
#    type=Column(reference=True, dtype=str, default="A")
#    )
#
#oo = Part(30, db, type="A", mount=False, tag=10)
#*tv, = oo.tweens()
#tv[0].set("mount", True)
#print([(k, [tvv.get(k) for tvv in oo.tweens()]) for k in oo.keys()])

class SS(StreamConnector):
    def __getitem__(self, item):
        # FIXME В перспективе это может стать долго
        #  ну и как минимум это игнорирует основные возможности предоставляемые redis
        _all = self.xrange(count=1, min=f'{item}', max="+")


        return _all


class RedisBind:
    def __new__(cls,  ref:dict, conn=None,name=f"api:mmcore:runtime:mfb:sw:l2:dbv232",interval=30*60*60, **kwargs):

        obj = super().__new__(cls)
        ss = SS(name, conn)
        obj.ref = ref
        obj.stream = ss
        obj.interval=interval
        if ss.xlen()==0:
            ref["part_db"] = Db(**kwargs)
            obj.dumps()
            obj._last_save=time.time()
            print("content is created")

            return obj
        else:
            print("content is loaded")
            obj.loads()
            obj._last_save=time.time()
            return obj
    @property
    def db(self):
        return self.ref["part_db"]

    @db.setter
    def db(self,v):
        self.ref["part_db"]=v
    def dumps(self):
        _=self.stream.xadd(None, {"pkl": pickle.dumps(self.db)})
        self._last_save=time.time()
        self._log.append(( self._last_save,_))
        return _
    def loads(self, i=None):
        if i is None:
            jj = self.stream.get_last()

            self.db=pickle.loads(jj[0][1][b'pkl'])
        else:
            self.db=pickle.loads(
                self.stream[i][0][1][b'pkl'])
        return self.db
    _stop=False
    _last_save=None
    _log=[]
    def stop(self):
        self._stop=True
        self.thr.join(1)
        self._stop=False
    def start(self):
        import threading as th

        def ww():
            while True:
                if self._stop:
                    print("stopping")
                    break

                else:
                    if time.time()-self._last_save>=self.interval:
                        if pickle.dumps(self.db) != pickle.dumps(self.loads()):
                            self._last_save = time.time()
                            dm=self.dumps()

                        else:

                            self._last_save = time.time()
                            self._log.append(( self._last_save, "No Changes"))

                    else:
                        time.sleep(5)

        self.thr=th.Thread(target=ww)
        self.thr.start()
