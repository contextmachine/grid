import dotenv,os

from src.preprocess.settings import SW_W_PATHS

dotenv.load_dotenv(os.getcwd()+"/.env")
import copy
import json
from src.cxm_props import PROJECT, BLOCK, ZONE
from mmcore.services.redis.connect import get_cloud_connection
rconn = get_cloud_connection()
class SvetaJson:
    def __init__(self, data):
        super().__init__()
        self._data=data
        self._store=dict()
        self.keys=self.extract_keys()
        self.check_len()
    @property
    def data(self):
        return self._data
    def extract_keys(self):
        ks = []
        self._store["key_index"]=dict()
        for item in self.data:
            for k in item.keys():
                
                self._store["key_index"][k]=len(ks)
                ks.append(k)
            
        return ks
    def extract_vals(self):
        ks = []
        
        for item in self.data:
            ks.extend(list(item.values()))
        return ks
    def check_len(self):
        lens=[len(list(item.values())[0])  for item in self.data]
        
            
        if not len(set(lens))==1:
            raise Exception(f"len raise {lens}")
    def length(self):
        lens = [len(list(item.values())[0]) for item in self.data]
        return lens[0]
    
    def prettify(self):...
    
    def __getitem__(self, key):
        return self._data[self._store["key_index"][key]][key]
    def __setitem__(self, key, val):    
        
        self._data[self._store["key_index"][key]][key]=val
        
    def merge(self, other):
        new=SvetaJson(copy.deepcopy(self._data))
        for k in self.keys:
            new[k]=self[k]+other[k]
        return new
    def dump(self, path):
        with open(path, "w") as f:
            json.dump(self._data, f)

    def dumps(self):

        return json.dumps(self._data)


def merge(target, parts):
    d=None
    for i in parts:
        with open(i, "rb") as f:

            _d = SvetaJson(json.load(f))
            if d is None:
                d = _d
            else:
                d = d.merge(_d)
    d.dump(target)
    return d
def redis_key( project_block_zone=(PROJECT,BLOCK,ZONE)):
    p,b,z=project_block_zone
    return f"api:mmcore:runtime:{p.lower()}:{b.lower()}:{z.lower()}:datapoints"
def to_redis( data, key=redis_key(), conn=rconn):
    return conn.set(key, json.dumps(data))
def alltasks(target=f"{os.getcwd()}/all_types.json", parts=SW_W_PATHS, key=redis_key(), conn=rconn):
    print(key)
    return to_redis( merge(target, parts=parts)._data, key=key, conn=conn)