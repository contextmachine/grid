import os
import pickle

import dotenv
from mmcore.base.tags import TagDB

dotenv.load_dotenv(dotenv_path=".env")

from src.cxm_props import PROJECT,BLOCK,ZONE
from mmcore.services.redis.connect import get_cloud_connection
from mmcore.services.redis import sets
rconn = get_cloud_connection()
sets.rconn = rconn
rmasks = sets.Hdict(f"{PROJECT}:{BLOCK}:{ZONE}:masks")
cols = dict(sets.Hdict(f"{PROJECT}:{BLOCK}:{ZONE}:colors"))

if os.getenv("TEST_DEPLOYMENT") is not None:
    TAGDB=f"api:mmcore:runtime:{PROJECT}:{BLOCK}:{ZONE}:tagdb_test"

else:
    TAGDB=f"api:mmcore:runtime:{PROJECT}:{BLOCK}:{ZONE}:tagdb"
props_table = rconn.get(TAGDB)

if props_table is None:
    props_table = TagDB(f"{PROJECT}_{BLOCK}_{ZONE}_panels")

else:
    props_table=pickle.loads(props_table)
print(props_table)
props_table.add_column("mount", default=False, column_type=bool)

props_table.add_column("mount_date", default="", column_type=str)
