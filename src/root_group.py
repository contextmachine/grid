import datetime
import time

import ujson
from mmcore.base import AGroup, adict, idict
from src.props import props_table, colormap
from mmcore.base.registry import adict, idict
from threading import Thread

def date():
    now = datetime.datetime.now()
    y, m, d = now.year, str(now.month), str(now.day)
    if len(m) == 1:
        m = f"0{m}"
    if len(d) == 1:
        d = f"0{d}"

    return f'{y}:{m}:{d}'


class RootGroup(AGroup):

    def props_update(self, uuids: list[str], props: dict):
        global reflection

        if "mount" in props.keys():
            if props.get("mount") is not None:
                if props.get("mount"):
                    props["mount_date"] = date()
                else:
                    props["mount_date"]=""

        for uuid in uuids:
            props_table[uuid].set(props)

        return True

    def root(self, shapes=None):
        # colormap.reload()
        return super().root(shapes=shapes)

    @property
    def children_uuids(self):
        return idict[self.uuid]["__children__"]

    @property
    def children(self):
        return [adict[child] for child in self.children_uuids]


class MaskedRootGroup(RootGroup):
    _mask_name = None
    _owner_uuid = ''
    _children_uuids = None
    cache=None
    def props_update(self, uuids: list[str], props: dict):
        #recompute_mask = False
        print(props)
        s=time.time()
        #if self.mask_name in props.keys():
            #recompute_mask = True

        ans = super().props_update(uuids, props)
        #if recompute_mask:
            #self.recompute_mask()
        self.make_cache()
        m,sec = divmod(time.time()-s,60)
        print(f'updated at {m} min, {sec} sec')
        return ans

    def make_cache(self):
        sup=super()

        def asyncache():
            #print("caching...")
            self.cache = sup.root()
            #print("done")
        asyncache()
        #self._th=Thread(target=asyncache)
        #self._th.start()


    def root(self, shapes=None, dumps=False):
        if self.cache is None:
            self.make_cache()
        #if self._th.is_alive():
            #self._th.join(0.5)

        return self.cache

    @property
    def owner_uuid(self):
        return self._owner_uuid

    @owner_uuid.setter
    def owner_uuid(self, v):
        self._owner_uuid = v

    @property
    def owner(self):
        return adict.get(self._owner_uuid)

    @property
    def mask_table(self):
        return props_table

    @property
    def mask_name(self):
        return self._mask_name

    @mask_name.setter
    def mask_name(self, v):
        self._mask_name = v
        self.recompute_mask()

    def recompute_mask(self):
        self._children_uuids = list(filter(self.filter_children, idict[self.owner_uuid]["__children__"]))
        self.make_cache()




    @property
    def children_uuids(self):
        if self._children_uuids is None:
            self.recompute_mask()
        return self._children_uuids

    def filter_children(self, x):
        return self.mask_table[x][self.mask_name] <= 1
