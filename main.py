import gzip
import json
import pickle
import dataclasses
import click
import uvicorn
import os
import dotenv
import numpy as np
import pandas as pd


dotenv.load_dotenv(dotenv_path=".env")
reflection = dict(recompute_repr3d=True, mask_index=dict())
from src.props import TAGDB
from copy import deepcopy
from fastapi import FastAPI, UploadFile
from starlette.responses import FileResponse, HTMLResponse
from scipy.spatial import KDTree

from src.cxm_props import BLOCK, PROJECT, ZONE

from mmcore.geom.materials import ColorRGB
from mmcore.base import A, AGroup, AMesh
from mmcore.base.components import Component
from mmcore.base.sharedstate import serve
from mmcore.base.registry import adict, idict
from mmcore.geom.shapes.base import Triangle
from mmcore.geom.point import GeometryBuffer, BUFFERS
from mmcore.services.redis.connect import get_cloud_connection
from mmcore.services.redis import sets
from mmcore.base import ALine, A, APoints, AGroup
from mmcore.base.tags import TagDB
print(TAGDB)
from src.pairs import gen_pair_stats,gen_stats_to_pairs,solve_pairs_stats
from src.parts import Column, Db, Part, RedisBind

# This Api provides an extremely flexible way of updating data. You can pass any part of the parameter dictionary
# structure, the parameters will be updated recursively and only the part of the graph affected by the change
# will be recalculated.
reflection["tri_items"] = dict()
A.__gui_controls__.config.address = os.getenv("MMCORE_ADDRESS")
A.__gui_controls__.config.api_prefix = os.getenv("MMCORE_APPPREFIX")
from src.props import rconn, cols, rmasks
from src.root_group import RootGroup, props_table, MaskedRootGroup


#props_table = TagDB("mfb_sw_l2_panels")


def prettify(dt, buff=None):
    if buff is None:
        reflection["data_pts"] = []
        buff = reflection["data_pts"]

    for x, y, z, archtype, engtype, block, zone in zip(
            list(dt[0].values())[0],
            list(dt[1].values())[0],
            list(dt[2].values())[0],
            list(dt[3].values())[0],
            list(dt[4].values())[0],
            list(dt[5].values())[0],
            list(dt[6].values())[0]):
        pt = [float(x), float(y), float(z)]

        buff.append(pt)
        ptr = len(buff) - 1

        if engtype is None:
            engtype = 0

        yield {
            "center": ptr,
            "arch_type": archtype,
            "eng_type": engtype,
            "block": block,
            "zone": zone
        }


class Buf(GeometryBuffer):
    def append(self, item):
        return super().add_item(item)


with open("swdata/masks/cut.json", "r") as msk:
    projmask =    cut= json.load(msk)
    rmasks["cut_mask"] =cut
    rmasks['projmask'] =cut
    cut_mask=rmasks["cut_mask"]
    #projmask = projmask[1930:1955]
    #mask_db.cols['cut_mask'].set_data(dict(enumerate(cut)))
    #mask_db.cols['projmask'].set_data(dict(enumerate(cut)))

    #projmask = projmask[1930:1955]

with open("swdata/SW_triangles_cutted.gz", "rb") as msk:
    tri = json.loads(gzip.decompress(msk.read()).decode())
    #tri = tri[1930:1955]


with open("swdata/SW_triangles.gz", "rb") as msk:
    tri_no_cut = json.loads(gzip.decompress(msk.read()).decode())
    #tri_no_cut=tri_no_cut[1930:1955]

with open("swdata/SW_centers.json", "r") as msk:
    tri_cen = json.load(msk)
    #tri_cen = tri_cen[1930:1955]

with open("swdata/SW_names.json", "r") as msk:
    tri_names = json.load(msk)

    #tri_names = tri_names[1930:1955]



Triangle.table = GeometryBuffer(uuid='default')

itm2 = []

arr = np.asarray(tri_cen).reshape((len(tri_cen), 3))
arr[..., 2] *= 0


def check_mask(mask):
    _masks = dict(rmasks)

    def m(x):
        return mask[x[0]] if x[0] in mask.keys() else False

    return filter(m, _masks.items())


def solve_kd(new_data):

    dt = list(prettify(new_data))
    reflection['data'] = dt

    vg = np.array(reflection["data_pts"])
    vg[..., 2] *= 0

    kd = KDTree(vg)
    reflection["kd"] = kd
    dist, ix = reflection['kd'].query(arr, distance_upper_bound=200)

    reflection["ix"] = ix
    reflection["recompute_repr3d"]=True


class PanelMesh(AMesh):
    @property
    def properties(self):
        return props_table[self.uuid]

    @properties.setter
    def properties(self, props: dict):
        props_table[self.uuid].set(dict(props))


class CompoundPanel(A):
    '''@property
    def properties(self):
        return props_table[self.uuid]
    @properties.setter
    def properties(self, props: dict):
        props_table[self.uuid].set(dict(props))'''


def solve_triangles():
    for i, j in enumerate(reflection['ix']):
        try:
            reflection["data"][j]
        except IndexError:
            #print(False)
            j = j - 1
        tag = f'{reflection["data"][j]["arch_type"]}-{reflection["data"][j]["eng_type"]}'
        if tag not in cols:
            cols[tag] = np.random.randint(30, 230, 3).tolist()
        for ppp in tri[i]:


            uuid = tri_names[i].replace(":", "_")




            reflection["mask_index"][uuid]=i

            props_table[uuid]["tag"] = tag

            props_table[uuid] = reflection['data'][j]
            props_table[uuid]["cut"] = cut_mask[i]
            props_table[uuid]["cut_mask"] = cut_mask[i]
            props_table[uuid]["projmask"] = cut_mask[i]

            if uuid not in reflection["tri_items"].keys():

                if len(ppp) > 1:

                    pan = CompoundPanel(uuid=uuid, name=tri_names[i].replace(":", "_"),
                                        _endpoint="triangle_handle/" + uuid,
                                        )
                    # pan.controls = props_table[uuid]
                    pan._endpoint = "triangle_handle/" + uuid

                    for k, pts in enumerate(ppp):
                        #mask_db.index_map.append(i)
                        #prt=Part(i+k, mask_db)
                        #prt.set('self_uuid', uuid + f"_{k + 1}")



                        new_props = deepcopy(props_table[uuid])
                        #print(new_props)
                        d=dict(new_props)
                        if "mount" in d.keys():
                            mnt=d.pop("mount")
                        else:
                            props_table.add_column("mount", default=0,column_type=int)
                            mnt=0

                        try:
                            props_table[uuid + f"_{k + 1}"].set(d)
                            props_table.columns["mount"][uuid + f"_{k + 1}"]=mnt
                            #print('got it 1')
                        except:
                            props_table[uuid + f"_{k + 1}"] = d
                            props_table.columns["mount"][uuid + f"_{k + 1}"] = mnt
                            #print('got it 2')

                        trii = Triangle(*pts)
                        trii.triangulate()
                        panel = trii.mesh_data.to_mesh(cls=PanelMesh,
                                                       uuid=uuid + f"_{k + 1}",
                                                       name=uuid + f"_{k + 1}",
                                                       color=ColorRGB(*cols[tag]).decimal,
                                                       _endpoint="triangle_handle/" + uuid,
                                                       )

                        panel.controls = props_table[uuid + f"_{k + 1}"]
                        panel._endpoint = "triangle_handle/" + uuid + f"_{k + 1}"

                        pan.__setattr__(f"part{k + 1}", panel)

                    reflection["tri_items"][uuid ] = pan
                else:
                    #mask_db.index_map.append(i)
                    #prt = Part(i, mask_db)
                    #prt.set('parent_uuid', uuid)
                    #prt.set('self_uuid', uuid)

                    trii = Triangle(*ppp[0])
                    trii.triangulate()
                    pan = trii.mesh_data.to_mesh(cls=PanelMesh,
                                                 uuid=uuid,
                                                 name=uuid,
                                                 color=ColorRGB(*cols[tag]).decimal,
                                                 _endpoint="triangle_handle/" + uuid,
                                                 )
                    pan.controls = props_table[uuid]
                    pan._endpoint = "triangle_handle/" + uuid
                    reflection["tri_items"][uuid] = pan


def masked_group1(owner_uuid, name,mode=True):
    global mask_db
    uid = f"{owner_uuid}_masked_{name}"
    if uid in adict.keys():
        grp = adict[uid]
    else:
        grp = RootGroup(name=adict[owner_uuid].name, uuid=f"{owner_uuid}_masked_{name}")
        grp.scale(0.001,0.001,0.001)

    if mode:
        idict[uid]["__children__"] = set(filter(lambda x: props_table[x][name] <= 1, idict[owner_uuid]['__children__']))
    else:
        idict[uid]["__children__"] = set(
            filter(lambda x: Part(list(mask_db.cols["self_uuid"].data.values()).index(x), mask_db).get(name) <= 1,
                   idict[owner_uuid]['__children__']))
    return grp




_dt = rconn.get(f"api:mmcore:runtime:{PROJECT}:{BLOCK}:{ZONE}:datapoints")

if _dt is not None:
    if isinstance(_dt, bytes):
        _dt = _dt.decode()
    solve_kd(json.loads(_dt))

def on_shutdown():
    return rconn.set(TAGDB, pickle.dumps(props_table))



solve_triangles()

grp = RootGroup(uuid=f"{PROJECT}_{BLOCK}_{ZONE}_panels", name=f"{BLOCK} {ZONE} panels".upper())

idict[f"{PROJECT}_{BLOCK}_{ZONE}_panels"]["__children__"] = set()


for i, uid in enumerate(reflection["tri_items"].keys()):
    print(f'solve {i} {uid}', flush=True, end="\r")
    idict[f"{PROJECT}_{BLOCK}_{ZONE}_panels"]["__children__"].add(uid)


grp.scale(0.001, 0.001, 0.001)


pgrp=MaskedRootGroup(uuid=f"{PROJECT}_{BLOCK}_{ZONE}_panels_masked_cut",
                name=f"{BLOCK} {ZONE}".upper(),
                mask_name="cut",
                owner_uuid=f"{PROJECT}_{BLOCK}_{ZONE}_panels")

pgrp.scale(0.001, 0.001, 0.001)
solve_pairs_stats(reflection=reflection,props=props_table)
print(pgrp.uuid)


@serve.app.get("/table")
async def stats1():
    tab = pd.DataFrame(props_table.columns)
    tab.to_csv("table.csv")
    return FileResponse("table.csv", filename="table.csv", media_type="application/csv")




@serve.app.post("/masks/add/{name}")
async def mask_handle(name, data: dict):
    #mm = dict(cmr.todict()['masks'])
    rmasks[name] = data["masks"]
    props_table.set_column(name, dict(zip(props_table.get_column("tag").keys(), data['masks'])))
    #mm[name] = data["state"]

    #cmr(masks=mm)
    #return mm


@serve.app.post("/masks/v2/add/{uuid}/{name}")
async def mask_handle_v2(uuid:str, name:str, data: dict):
    #mask_db.cols[name]=Column(reference=data['reference'], dtype=int)
    #mask_db.cols[name].set_data(dict(enumerate(data["masks"])))
    if 'masks' in data.keys():
        props_table.set_column(name, dict(zip(props_table.get_column("tag").keys(), data['masks'])))
    grp=masked_group1(uuid,name)
    #props_table.set_column(name, dict(zip(props_table.get_column("tag").keys(), data['masks'])))
    #mask_db.cols[name]=Column(**data)
    #rmask_db.dumps()

    return grp.root()

@serve.app.post("/triangle_handle/{uid}")
async def triangle_handle(uid, properties: dict):
    props_table[uid].set(properties)

    adict[uid].controls = props_table[uid]
    return dict(props_table[uid])

@serve.app.get("/triangle_handle/{uid}")
async def triangle_handle_get(uid: str):
    return props_table[uid]




if os.getenv("TEST_DEPLOYMENT") is None:
    @serve.app.post("/upload_json")
    async def create_upload_file(file: UploadFile):
        try:

            content = await file.read()

            rconn.set(f"api:mmcore:runtime:{PROJECT}:{BLOCK}:{ZONE}:datapoints", content.decode())
            solve_kd(json.loads(content.decode()))

            solve_triangles()
            #cmr()

            solve_pairs_stats(reflection=reflection, props=props_table)

            # path=os.getcwd()+"/model.3dm"
            # obj.dump3dm().Write(path,7)

            return "Ok"
        except Exception as err:
            return f"error: {err}"


    @serve.app.get("/upload_form")
    async def upjf():
        content = f"""
    
    <body>
    </form>
    <form action="{os.getenv("MMCORE_ADDRESS")}{os.getenv("MMCORE_APPPREFIX")}upload_json" enctype="multipart/form-data" method="post">
    <input name="file" type="file">
    <input type="submit">
    </form>
    </body>
        """
        return HTMLResponse(content=content)

@serve.app.get("/stats")
def stats():
    return list(gen_stats_to_pairs(props_table=props_table))
@serve.app.get("/stats/pairs")
def stats_pairs():

    return reflection["pairs_stats"]

if os.getenv("TEST_DEPLOYMENT") is None:
    aapp = FastAPI(on_shutdown=[on_shutdown])
else:
    aapp = FastAPI()
aapp.mount(os.getenv("MMCORE_APPPREFIX"), serve.app)


if __name__ == "__main__":
    uvicorn.run("main:aapp", host='0.0.0.0', port=7711)
