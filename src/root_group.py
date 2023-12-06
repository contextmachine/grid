import dataclasses
import datetime
import time
from enum import Enum

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

class EntryProtocol(str,Enum):
    REST = "REST"
    WS="WS"
    GRAPHQL = "GRAPHQL"

@dataclasses.dataclass
class EntryEndpoint:
    protocol:str
    url:str
@dataclasses.dataclass
class Entry:
    name:str
    endpoint: EntryEndpoint
    def __eq__(self, other):
        return self.name==str(getattr(other,'name',None))
    def __hash__(self):
        return hash(self.name)


def add_entry_safe(entries:list, entry:Entry):
    if entry not in entries:
        entries.append(entry)
"""
{
  "name": "root",
  "userData": {
    "entries":[
    {
      "name": "update_props",
      "endpoint": {
        "protocol": "REST",
        "url": "..."
      }
    },
    {
      "name": "control_points",
      "endpoint": {
        "protocol": "WS",
        "url": "..."
       }
     }
   ]
  }
}
"""
def asdict(obj):
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    elif isinstance(obj,(list,tuple,set)):
        return [asdict(o)for o in obj]
    elif isinstance(obj,dict):
        return {k:asdict(o) for k,o in obj.items()}
    else:
        return obj

class MaskedRootGroup(RootGroup):
    _mask_name = None
    _owner_uuid = ''
    _children_uuids = None

    _user_data_extras = None
    cache=None


    def __new__(cls, *args,user_data_extras=None,entries_support=True,props_update_support=True, **kwargs):
        if user_data_extras is None:
            user_data_extras=dict()
        obj=super().__new__(cls,*args,_user_data_extras= user_data_extras,**kwargs)


        return obj
    @property
    def object_url(self):
        return self.__class__.__gui_controls__.config.address + self.__class__.__gui_controls__.config.api_prefix

    def add_entry(self, entry:Entry):
        add_entry_safe(self._user_data_extras['entries'], entry)

    @property
    def has_entries(self):
        return 'entries' in self._user_data_extras

    def add_entries_support(self):
        if not self.has_entries:
            self.add_user_data_extra("entries", [])
    def add_props_update_support(self):
        if not self.has_entries:
            self.add_entries_support()

        self.add_entry(Entry(name="update_props",
                             endpoint=EntryEndpoint(protocol="REST",
                                                    url=self.object_url+f"props-update/{self.uuid}")))

    def add_user_data_extra(self, key, value):
        if key not in self._user_data_extras:
            self._user_data_extras[key]=value
        else:
            pass
    @property
    def entries(self):
        return self._user_data_extras.get('entries', None)
    @entries.setter
    def entries(self, v):
        self._user_data_extras['entries']=v

    def update_entries(self, v):
        if 'entries' not in self._user_data_extras:

            self.entries=v
        else:
            self._user_data_extras['entries'] = v

    def __call__(self, *args, **kwargs):
        dct=super().__call__(*args, **kwargs)
        dct['userData']|= asdict(self._user_data_extras)
        return dct
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
