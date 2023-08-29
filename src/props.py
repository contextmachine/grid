import os
import pickle

import dotenv
from mmcore.base.tags import TagDB

dotenv.load_dotenv(dotenv_path=".env")
reflection = dict(recompute_repr3d=True, mask_index=dict())

from mmcore.services.redis.connect import get_cloud_connection
from mmcore.services.redis import sets
rconn = get_cloud_connection()
sets.rconn = rconn
rmasks = sets.Hdict("mfb:sw:l1:masks")
cols = dict(sets.Hdict("mfb:sw:l2:colors"))
reflection["tri_items"] = dict()
if os.getenv("TEST_DEPLOYMENT") is not None:
    TAGDB=f"api:mmcore:runtime:mfb:sw:l2:tagdb_test"

else:
    TAGDB=f"api:mmcore:runtime:mfb:sw:l2:tagdb"
props_table = rconn.get(TAGDB)

if props_table is None:
        props_table = TagDB("mfb_sw_l2_panels")

else:
    props_table=pickle.loads(props_table)
print(props_table)

