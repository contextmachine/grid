import copy
import json
import os
import pickle

import dotenv
import numpy as np
from mmcore.base.tags import TagDB, __databases__
from mmcore.base.registry import amatdict
from mmcore.geom.materials import ColorRGB
from mmcore.base.geom import MeshPhongMaterial

dotenv.load_dotenv(dotenv_path=".env")

from src.cxm_props import PROJECT, BLOCK, ZONE, DB_NAME
from mmcore.services.redis.connect import get_cloud_connection, get_local_connection
from mmcore.services.redis import sets

if os.getenv("LOCAL_REDIS") == '1':
    rconn = get_local_connection()
else:
    rconn = get_cloud_connection()
sets.rconn = rconn
rmasks = sets.Hdict(f"{PROJECT}:{BLOCK}:{ZONE}:masks")
cols = dict(sets.Hdict(f"{PROJECT}:colors"))
PANEL_AREA=0.12
MIN_CUT=PANEL_AREA/3
base_gsh=json.loads("""{
  "sheet_id": "150p5C3tNDHt5KJylrcpwLpK0Wrgf6zjZDgFKL5vZypA",
  "main_sheet_range": "SW_L2_test!A1",
  "table_keys": [
    "name",
    "tag",
    "arch_type",
    "eng_type",
    "block",
    "zone",
    "cut",
    "pair_name",
    "pair_index",
    "mount",
    "mount_date",
    "area"
  ],
  "writes": [
    {
      "sheet_range": "SW_L2_pair_count_test!A2",
      "key": "arch_type",
      "mask": "cut",
      "sep": " "
    },
    {
      "sheet_range": "SW_L2_pair_count_test!G2",
      "key": "tag",
      "mask": "cut",
      "sep": " "
    }
  ],
  "enable": true
}""")
if os.getenv("TEST_DEPLOYMENT")=="1":
    gsheet_spec=sets.Hset(f"{PROJECT}:gsheet_test").todict()

else:
    gsheet_spec = sets.Hset(f"{PROJECT}:gsheet").todict()
zone_scopes=dict(sets.Hdict(f"{PROJECT}:{BLOCK}:zone_scopes"))
zone_scopes_redis=sets.Hdict(f"{PROJECT}:{BLOCK}:zone_scopes")


def normalize_str(s) -> 'str|bytes':
    """
    >>> normalize_str('A')
    'A'
    >>> normalize_str('Ф')
    b'\xd0\xa4'
    """
    try:
        val = s.encode(encoding='utf-8').decode('ascii')
    except UnicodeDecodeError:

        return s.encode(encoding='utf-8', errors='replace')
    else:
        return val


class ColorMap(dict):
    def __init__(self, *args, hset_key=f"{PROJECT}:colors", **kwargs):
        self._hset = sets.Hdict(hset_key)
        super().__init__(*args, **kwargs)
        self._store = dict()
        self.update(dict(self._hset))

    def __setitem__(self, k, item):
        if k not in self.keys():
            k=normalize_str(k)
            self._hset[k] = item
            # mat=MeshPhongMaterial(color=ColorRGB(*item).decimal)

            self._store[k] = self.solve_item(item)
        super().__setitem__(k, item)

    def __getitem__(self, item):
        item=normalize_str(item)
        if item not in self._store:
            if item not in self._hset:
                self._hset[item] = np.random.randint(30, 220, size=3).tolist()

            self._store[item] = self.solve_item(self._hset[item])
        return self._store[item]

    def reload(self):
        self._store = dict()
        self.update(dict(self._hset))

    def solve_item(self, item):
        col = ColorRGB(*item).decimal
        mat = f"{col}meshphongmaterial"
        if mat not in amatdict:
            amatdict[mat] = MeshPhongMaterial(color=ColorRGB(*item).decimal)

        return mat


colormap = ColorMap()


class ColumnType(dict):
    def __init__(self, ownid=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(ownid, TagDB):
            self.ownid = ownid.uuid
        else:
            self.ownid = ownid

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
        self._own.columns["eng_type"][k] = b

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

        state = copy.deepcopy(super().__getstate__())
        state["columns"]["tag"] = dict()
        #self.columns['tag'] = SolvedTagColumn(self.uuid)
        return state

    def __setstate__(self, state):
        super().__setstate__(state)
        self.columns['tag'] = SolvedTagColumn(self.uuid)


if os.getenv("TEST_DEPLOYMENT") is not None:
    TAGDB = f"api:mmcore:runtime:{PROJECT}:{BLOCK}:{ZONE}:{DB_NAME}_test"

else:
    TAGDB = f"api:mmcore:runtime:{PROJECT}:{BLOCK}:{ZONE}:{DB_NAME}"
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
