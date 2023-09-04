import os
import pickle

import dotenv
from mmcore.base.tags import TagDB, __databases__

dotenv.load_dotenv(dotenv_path=".env")

from src.cxm_props import PROJECT, BLOCK, ZONE
from mmcore.services.redis.connect import get_cloud_connection
from mmcore.services.redis import sets

rconn = get_cloud_connection()
sets.rconn = rconn
rmasks = sets.Hdict(f"{PROJECT}:{BLOCK}:{ZONE}:masks")
cols = dict(sets.Hdict(f"{PROJECT}:{BLOCK}:{ZONE}:colors"))

class ColumnType(dict):
    def __init__(self, ownid=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(ownid, TagDB):
            self.ownid = ownid.uuid
        else:
            self.ownid= ownid
    @property
    def _own(self):
        return __databases__.get(self.ownid)
    def __getstate__(self):
        return {"ownid": self.ownid, "state": dict(self)}
    def __setstate__(self, state):
        self.ownid = state.get("ownid")
        self.update(state["state"])



class SolvedTagColumn(ColumnType):


    @property
    def _own(self):

        return __databases__.get(f"{PROJECT}_{BLOCK}_{ZONE}_panels")
    def __getitem__(self, item):
        return f'{self._own.columns["arch_type"].get(item, self._own.defaults["arch_type"])}-{self._own.columns["eng_type"].get(item, self._own.defaults["eng_type"])}'

    def __setitem__(self, k, item):
        a, b = item.split("-")

        self._own.columns["arch_type"][k] = a
        self._own.columns["eng_type"][k] = int(b)

    def keys(self):
        return self._own.columns["arch_type"].keys()

    def values(self):
        for k in self._own.columns["arch_type"].keys():
            yield self[k]

    def items(self):
        for k in self._own.columns["arch_type"].keys():
            yield k, self[k]

    def update(self, value) -> None:
        for k, v in value.items():
            self.__setitem__(k, v)

    def __ior__(self, other):
        for k, v in other.items():
            self.__setitem__(k, v)
        return self

    def get(self, v, default):
        vl = self[v]

        return default if vl is None else vl

class PanelsTagDB(TagDB):
    def __getstate__(self):
        state=super().__getstate__()
        state["columns"]["tag"]=dict()
        return state
    def __setstate__(self, state):
        super().__setstate__(state)
        self.columns['tag'] = SolvedTagColumn(self.uuid)

if os.getenv("TEST_DEPLOYMENT") is not None:
    TAGDB = f"api:mmcore:runtime:{PROJECT}:{BLOCK}:{ZONE}:tagdb_test"

else:
    TAGDB = f"api:mmcore:runtime:{PROJECT}:{BLOCK}:{ZONE}:tagdb1"
props_table = rconn.get(TAGDB)




if os.getenv("RECREATE_TAGDB"):
    print("Tag DB recreate ...")
    props_table = PanelsTagDB(f"{PROJECT}_{BLOCK}_{ZONE}_panels")
    props_table.add_column("mount", default=False, column_type=bool)

    props_table.add_column("mount_date", default="", column_type=str)
    props_table.add_column("tag", default="", column_type=str)
    props_table.columns['tag'] = SolvedTagColumn(props_table.uuid)
elif props_table is None:
    props_table = PanelsTagDB(f"{PROJECT}_{BLOCK}_{ZONE}_panels")
    props_table.add_column("mount", default=False, column_type=bool)

    props_table.add_column("mount_date", default="", column_type=str)
    props_table.add_column("tag", default="", column_type=str)
    props_table.columns['tag'] = SolvedTagColumn(props_table.uuid)
else:
    props_table = pickle.loads(props_table)
#
print(props_table)