import gzip
import json
import pickle

import click
import uvicorn
from fastapi import FastAPI, UploadFile
from fastapi.openapi.models import Response
from mmcore.base.registry import adict, idict
from starlette.responses import FileResponse, HTMLResponse

from mmcore.base import A, AGroup, AMesh
from mmcore.base.components import Component
from mmcore.base.sharedstate import serve
from mmcore.geom.point import GeometryBuffer, BUFFERS
import dataclasses
from mmcore.geom.shapes.base import Triangle
import os

from mmcore.base import ALine, A, APoints, AGroup

# This Api provides an extremely flexible way of updating data. You can pass any part of the parameter dictionary
# structure, the parameters will be updated recursively and only the part of the graph affected by the change
# will be recalculated.

reflection = dict()
import json
import dotenv
dotenv.load_dotenv(dotenv_path=".env" )
import click
A.__gui_controls__.config.address=os.getenv("MMCORE_ADDRESS")
A.__gui_controls__.config.api_prefix=os.getenv("MMCORE_APPPREFIX")

from mmcore.geom.point import GeometryBuffer, BUFFERS
import dataclasses

reflection = dict()
from mmcore.services.redis.connect import get_cloud_connection
from mmcore.services.redis import sets
rconn=get_cloud_connection()
sets.rconn=rconn
def prettify(dt, buff=None):

    if buff is None:
        reflection["data_pts"]=[]
        buff = reflection["data_pts"]

    for x, y, z, archtype, engtype, block, zone in zip(
            list(dt[0].values())[0],
            list(dt[1].values())[0],
            list(dt[2].values())[0],
            list(dt[3].values())[0],
            list(dt[4].values())[0],
            list(dt[5].values())[0],
            list(
                dt[6].values())[0]):
        pt = [float(x), float(y), float(z)]


        buff.append(pt)
        ptr = len(buff)-1

        if engtype is None:
            engtype = 0

        yield {
            "center": ptr,
            "arch_type": archtype,
            "eng_type": engtype,
            "block": block,
            "zone": zone
        }



import pickle

rmasks=sets.Hdict("mfb:sw:l1:masks")
cut_mask=rmasks["cut_mask"]
class Buf(GeometryBuffer):
    def append(self, item):
        return super().add_item(item)




from scipy.spatial import KDTree

with open("swdata/masks/_project.json", "r") as msk:
    projmask = json.load(msk)

with open("swdata/SW_triangles_cutted.gz", "rb") as msk:
    tri = json.loads(gzip.decompress(msk.read()).decode())

with open("swdata/SW_triangles.gz", "rb") as msk:
    tri_no_cut = json.loads(gzip.decompress(msk.read()).decode())

with open("swdata/SW_centers.json", "r") as msk:
    tri_cen = json.load(msk)

with open("swdata/SW_names.json", "r") as msk:
    tri_names = json.load(msk)


import numpy as np

Triangle.table = GeometryBuffer(uuid='default')

itm2 = []
from mmcore.geom.materials import ColorRGB
arr = np.asarray(tri_cen).reshape((len(tri_cen), 3))
arr[..., 2] *= 0
def check_mask(mask):
    _masks=dict(rmasks)
    def m(x):
        return mask[x[0]] if x[0] in mask.keys() else False

    return filter(m, _masks.items())


def solve_kd(new_data):

    dt= list(prettify(new_data))
    reflection['data']=dt
    vg = np.array(reflection["data_pts"])
    vg[..., 2] *= 0
    kd = KDTree(vg)
    reflection["kd"]=kd
    dist, ix = reflection['kd'].query(arr, distance_upper_bound=200)
    reflection["ix"]=ix

from mmcore.base import AGroup
"""
with open("/Users/andrewastakhov/Downloads/SW_L2(3).json", "r") as sf:
    _data = json.load(sf)

solve_kd(_data)
#dist, ix = kd.query(arr, distance_upper_bound=200)

"""
_dt=rconn.get(f"api:mmcore:runtime:mfb:sw:l2:datapoints")
if _dt is not None:
    if isinstance(_dt, bytes):
        _dt=_dt.decode()
    solve_kd(json.loads(_dt))

def colors_loader(defaults):
    try:
        with open(".mmcache/colors.json", "r") as cl:
            return json.load(cl)
    except FileNotFoundError as err:
        print(err)
        cols = dict()
        cols |= defaults
        return cols


from mmcore.base.tags import TagDB


from mmcore.base.tags import TagDB
props_table = TagDB("mfb_sw_l2_panels")


class PanelMesh(AMesh):
    @property
    def properties(self):
        return props_table[self.uuid]

    @properties.setter
    def properties(self, props: dict):
        props_table[self.uuid].set(dict(props))
class CompoundPanel(A):
    @property
    def properties(self):
        return props_table[self.uuid]

    @properties.setter
    def properties(self, props: dict):
        props_table[self.uuid].set(dict(props))

from mmcore.services.redis import sets
sets.rconn=rconn
reflection["tri_items"]=dict()
cols=dict(sets.Hdict("mfb:sw:l2:colors"))
cols["A-0"] = [90, 90, 90]
def solve_triangles():



    for i, j in enumerate(reflection['ix']):



            try:
                reflection["data"][j]
            except IndexError:
                j = j - 1

            tag = f'{reflection["data"][j]["arch_type"]}-{reflection["data"][j]["eng_type"]}'

            if tag not in cols:
                cols[tag] = np.random.randint(30, 230, 3).tolist()

            for ppp in tri[i]:
                uuid = tri_names[i].replace(":", "_")
                props_table[uuid]["tag"]=tag
                props_table[uuid] = reflection['data'][j]
                props_table[uuid]["cut"] = cut_mask[i]
                if uuid not in reflection["tri_items"].keys():
                    #print(uuid)

                    if len(ppp)>1:

                        pan=CompoundPanel(uuid= uuid, name=tri_names[i].replace(":", "_"),
                                          _endpoint="triangle_handle/" + uuid,

                                          )

                        pan.controls = props_table[uuid]
                        pan._endpoint = "triangle_handle/" + uuid


                        for k, pts in enumerate(ppp):
                            trii = Triangle(*pts)
                            trii.triangulate()
                            pan.__setattr__(f"part{k+1}", trii.mesh_data.to_mesh(cls=AMesh,
                                                         uuid=uuid + f"_{k+1}",
                                                         name=uuid + f"_{k+1}",
                                                         color=ColorRGB(*cols[tag]).decimal,
                                            _endpoint= "triangle_handle/" + uuid,
                                                                                 properties=props_table[uuid],
                                             )

                                            )


                        reflection["tri_items"][uuid] = pan


                    else:
                        trii = Triangle(*ppp[0])
                        trii.triangulate()
                        pan=trii.mesh_data.to_mesh(cls=PanelMesh,
                                                                               uuid=uuid ,
                                                                               name=uuid ,


                                                                               color=ColorRGB(*cols[tag]).decimal,

                                                    _endpoint = "triangle_handle/" + uuid,
                                                   )
                        pan.controls = props_table[uuid]
                        pan._endpoint = "triangle_handle/" + uuid
                        reflection["tri_items"][uuid] = pan






solve_triangles()
for _k,_v in dict(rmasks).items():

    props_table.set_column(_k, dict(zip(props_table.get_column("tag").keys(),_v)))

class MaskedRequest(Component):

    masks:dict={}

    _itms=dict()
    def __call__(self, masks=None,**kwargs):

        if masks is not None:
            super().__call__(masks=masks,**kwargs)
        else:
            super().__call__(**kwargs)

        if "kd" in reflection.keys():
            self.__repr3d__()
        return self

    def __repr3d__(self):
        global props_table

        grp = AGroup(uuid="mfb_sw_l2_panels", name="SW L2 panels", _endpoint=self.endpoint, controls=self.param_node.todict())
        idict["mfb_sw_l2_panels"]["__children__"] = set()
        msks=dict(check_mask(self.masks))

        for i, uid in enumerate(reflection["tri_items"].keys()):

            if all([vl[i] <= 1 for  vl in msks.values()]):

                idict["mfb_sw_l2_panels"]["__children__"].add(uid)

        grp.scale(0.001, 0.001, 0.001)

        self._repr3d=grp

        return self._repr3d



cmr = MaskedRequest(uuid="mfb_sw_l2_panels", name="mfb_sw_l2_panels", masks={
    "projmask":True,
    "cut_mask": False
})

import pandas as pd


@serve.app.get("/table")
async def stats1():
    tab = pd.DataFrame(props_table.columns)
    tab.to_csv("table.csv")
    return FileResponse("table.csv", filename="table.csv", media_type="application/csv")


@serve.app.post("/triangle_handle/{uid}")
async def triangle_handle(uid, properties: dict):
    props_table[uid].set(properties)


    adict[uid].controls=props_table[uid]
    return dict(props_table[uid])
@serve.app.post("/masks/add/{name}")
async def mask_handle(name, data: dict):
    print(name, data)
    mm=dict(cmr.todict()['masks'])
    rmasks[name] = data["masks"]
    props_table.set_column(name, dict(zip(props_table.get_column("tag").keys(), data['masks'])) )
    mm[name]=data["state"]
    cmr(masks=mm)
    return mm
@serve.app.get("/triangle_handle/{uid}")
async def triangle_handle_get(uid:str):

    return props_table[uid]

@serve.app.post("/upload_json")
async def create_upload_file(file: UploadFile):
    try:

        content = await file.read()

        rconn.set(f"api:mmcore:runtime:mfb:sw:l2:datapoints", content.decode())
        solve_kd(json.loads(content.decode()))
        solve_triangles()
        cmr()
        #path=os.getcwd()+"/model.3dm"
        #obj.dump3dm().Write(path,7)

        return "Ok"
    except Exception as err:
        return f"error: {err}"
@serve.app.get("/upload_form")
async def upjf():

    content = f"""

<body>
</form>
<form action="{os.getenv("MMCORE_APPPREFIX")}upload_json" enctype="multipart/form-data" method="post">
<input name="file" type="file">
<input type="submit">
</form>
</body>
    """
    return HTMLResponse(content=content)


@serve.app.post("table/{name}")
def stats(name: str, data: dict):

    tab = pd.DataFrame(cmr(mask_name=name, mask_buffer=data["mask"])._itm2)
    tab.to_csv("table.csv")
    return FileResponse("table.csv", filename="table.csv", media_type="application/csv")



app=FastAPI()
app.mount(os.getenv("MMCORE_APPPREFIX"), serve.app)
if __name__=="__main__":
    uvicorn.run("main:app",host='0.0.0.0', port=7711)