import gzip
import json
import pickle

import uvicorn
import os
import dotenv
import numpy as np
import pandas as pd

dotenv.load_dotenv(dotenv_path=".env")
reflection = dict(recompute_repr3d=True, mask_index=dict(), cutted_childs=dict(),tris_rg=dict())
from src.props import TAGDB,colormap, rconn, cols, rmasks, ColorMap

from fastapi import FastAPI, UploadFile
from starlette.responses import FileResponse, HTMLResponse
from scipy.spatial import KDTree

from src.cxm_props import BLOCK, PROJECT, ZONE

from mmcore.geom.materials import ColorRGB
from mmcore.base import A, AGroup, AMesh

from mmcore.base.sharedstate import serve
from mmcore.base.registry import adict, idict
from mmcore.geom.shapes.base import Triangle
from mmcore.geom.point import GeometryBuffer, BUFFERS

from mmcore.base import ALine, A, APoints, AGroup

print(TAGDB)
from src.pairs import gen_pair_stats,gen_stats_to_pairs,solve_pairs_stats
from src.parts import Column, Db, Part, RedisBind

# This Api provides an extremely flexible way of updating data. You can pass any part of the parameter dictionary
# structure, the parameters will be updated recursively and only the part of the graph affected by the change
# will be recalculated.
reflection["tri_items"] = dict()
reflection["tris"] = list()
A.__gui_controls__.config.address = os.getenv("MMCORE_ADDRESS")
A.__gui_controls__.config.api_prefix = os.getenv("MMCORE_APPPREFIX")

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
def set_static_build_data(key, data, conn):
    return conn.set( key, gzip.decompress(json.dumps(data).encode()))
def get_static_build_data(key,conn):
    return json.loads(gzip.decompress(conn.get(key)).decode())

build=json.loads(gzip.decompress(rconn.get(f"{PROJECT}:{BLOCK}:{ZONE}:build")).decode())



cut, tri,  tri_cen ,tri_names= build['cut'],build['cutted_tri'],build['centers'], build['names']
projmask =    cut
rmasks["cut_mask"] =cut
rmasks['projmask'] =cut
cut_mask=rmasks["cut_mask"]

print(cols)
Triangle.table = GeometryBuffer(uuid='default')

itm2 = []

arr = np.asarray(tri_cen).reshape((len(tri_cen), 3))
#arr[..., 2] *= 0


def check_mask(mask):
    _masks = dict(rmasks)

    def m(x):
        return mask[x[0]] if x[0] in mask.keys() else False

    return filter(m, _masks.items())


def solve_kd(new_data):

    dt = list(prettify(new_data))
    reflection['data'] = dt

    vg = np.array(reflection["data_pts"])
    #vg[..., 2] *= 0

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

    @property
    def _material(self):
        return colormap[props_table[self.uuid]['tag']]

    @_material.setter
    def _material(self,v):
        print("ignore set material")
        pass

class CompoundPanel(A):
    '''@property
    def properties(self):
        return props_table[self.uuid]
    @properties.setter
    def properties(self, props: dict):
        props_table[self.uuid].set(dict(props))'''


def solve_triangles():
    reflection["tris"]=[]
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
            splitted_uuid = uuid.split("_")
            pair_name = splitted_uuid[3] + "_" + splitted_uuid[4]



            reflection["mask_index"][uuid]=i

            #props_table[uuid]["tag"] = tag
            for k,v in reflection['data'][j].items():
                column=props_table.columns[k]
                if uuid not in column.keys():
                    column[uuid]=v


            props_table[uuid]["cut"] = cut[i]
            props_table[uuid]["cut_mask"] = cut[i]
            props_table[uuid]["projmask"] = cut[i]

            # ADD PAIRS!
            props_table[uuid]["pair_name"] =  pair_name
            props_table[uuid]["pair_index"] = uuid[-1]
            # ADD PAIRS!

            if uuid not in reflection["tri_items"].keys():

                if len(ppp) > 1:

                    pan = CompoundPanel(uuid=uuid, name=tri_names[i].replace(":", "_"),
                                        _endpoint="triangle_handle/" + uuid,
                                        )
                    # pan.controls = props_table[uuid]
                    pan._endpoint = "triangle_handle/" + uuid
                    #reflection["cutted_childs"][uuid]=set()
                    for k, pts in enumerate(ppp):
                        #mask_db.index_map.append(i)
                        #prt=Part(i+k, mask_db)
                        #prt.set('self_uuid', uuid + f"_{k + 1}")



                        new_props = dict(props_table[uuid])
                        #d=dict(new_props)
                        #new_props["name"]=uuid + f"_{k + 1}"


                        #props_table.add_column("mount", default=0,column_type=int)
                        #mnt=0
                        #reflection["cutted_childs"][uuid].add(uuid + f"_{k + 1}")
                        try:
                            props_table[uuid + f"_{k + 1}"].set(new_props)
                            #props_table.columns["mount"][uuid + f"_{k + 1}"]=mnt

                            props_table.columns["pair_name"][uuid + f"_{k + 1}"] =  pair_name
                            props_table.columns["pair_index"][uuid + f"_{k + 1}"] = uuid[-1]

                        except:
                            props_table[uuid + f"_{k + 1}"].set(new_props)
                            #props_table.columns["mount"][uuid + f"_{k + 1}"] = mnt
                            props_table.columns["pair_name"][uuid + f"_{k + 1}"] = pair_name
                            props_table.columns["pair_index"][uuid + f"_{k + 1}"] = uuid[-1]

                        trii = Triangle(*pts)
                        #trii.triangulate()
                        geom=trii.mesh_data.create_buffer()
                        panel =PanelMesh(uuid=uuid + f"_{k + 1}", name=uuid + f"_{k + 1}", geometry=geom, _endpoint="triangle_handle/" + uuid + f"_{k + 1}")

                        #props_table["name"][uuid + f"_{k + 1}"] = uuid + f"_{k + 1}"
                        panel.controls = props_table[uuid + f"_{k + 1}"]
                        panel._endpoint = "triangle_handle/" + uuid + f"_{k + 1}"
                        reflection["tris"].append(props_table[uuid + f"_{k + 1}"])
                        pan.__setattr__(f"part{k + 1}", panel)

                    reflection["tri_items"][uuid] = pan
                else:
                    #mask_db.index_map.append(i)
                    #prt = Part(i, mask_db)
                    #prt.set('parent_uuid', uuid)
                    #prt.set('self_uuid', uuid)
                    #props_table["name"][uuid] = uuid
                    trii = Triangle(*ppp[0])
                    trii.triangulate()
                    geom = trii.mesh_data.create_buffer()
                    pan = PanelMesh(uuid=uuid , name=uuid , geometry=geom,
                                    _endpoint="triangle_handle/" + uuid )


                    pan.controls = props_table[uuid]
                    pan._endpoint = "triangle_handle/" + uuid
                    reflection["tri_items"][uuid] = pan

                    reflection["tris"].append(props_table[uuid])



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
    print("Grace Shutdown")
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

                owner_uuid=f"{PROJECT}_{BLOCK}_{ZONE}_panels")

pgrp.scale(0.001, 0.001, 0.001)
#solve_pairs_stats(reflection=reflection,props=props_table)
print(pgrp.uuid)
pgrp.mask_name="cut"

@serve.app.get("/table")
def stats1():
    tab = pd.DataFrame([dict(list(i)+[("name", i.index)]) for i in reflection["tris"]])
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

    if 'masks' in data.keys():
        props_table.set_column(name, dict(zip(props_table.get_column("tag").keys(), data['masks'])))
    grp=masked_group1(uuid,name)
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
async def stats():
    return [dict(list(i)+[("name", i.index)]) for i in reflection["tris"]]
@serve.app.get("/stats/pairs")
async def stats_pairs():

    return reflection["pairs_stats"]
@serve.app.get("/props_table")
def pt():
    with open("props_table.pkl", 'wb') as f:
        pickle.dump(props_table, f)
    return FileResponse(path="props_table.pkl", filename="props_table.pkl")


def rule(dct):
    def wrap(obj):
        if len(dct)==0:
            return False
        return all([obj[k] == dct[k] for k in dct.keys()])

    return wrap


@serve.app.post("/where")
def where_query(data: dict):
    rul = rule(data)
    return [dict(list(_i) + [("name", _i.index)]) for _i in list(filter(rul, reflection["tris"]))]

class TrisRGroup(RootGroup):


    @property
    def rule_data(self):
        return reflection["tris_rg"].get(self.uuid, dict())

    @rule_data.setter
    def rule_data(self,data):
        reflection["tris_rg"][self.uuid] =data
        self.controls=data

    @property
    def children_uuids(self):
        return set(itm.index for itm in filter(self.filter_children, reflection["tris"]))

    def filter_children(self, x):
        if len(self.rule_data) == 0:
            return False
        return all([x[k] == self.rule_data[k] for k in self.rule_data])


@serve.app.post("/where/{uid}")
async def where_obj(uid:str, data: dict):
    adict.get(uid).rule_data=data

    return data


@serve.app.get("/where/{uid}")
async def where_objget(uid: str):


    return adict.get(uid).rule_data


@serve.app.get("/dump/tagdb")
def dump_tagdb():
    on_shutdown()
    return TAGDB

@serve.app.get("/where/table")
def where_table(data: dict):
    rul = rule(data)
    tab = pd.DataFrame([dict(list(_i) + [("name", _i.index)]) for _i in list(filter(rul, reflection["tris"]))])
    tab.to_csv("table.csv")
    return FileResponse("table.csv", filename="table.csv", media_type="application/csv")

if os.getenv("TEST_DEPLOYMENT") is None:
    aapp = FastAPI(on_shutdown=[on_shutdown])
elif os.getenv('DUMP_TAGDB') =="1":
    aapp = FastAPI(on_shutdown=[on_shutdown])
else:
    aapp = FastAPI()
aapp.mount(os.getenv("MMCORE_APPPREFIX"), serve.app)

ttg = TrisRGroup(uuid="query_object", name="query_object", _endpoint="where/query_object", rule_data={"cut": 0})
ttg.scale(0.001,0.001,0.001)
if __name__ == "__main__":
    uvicorn.run("main:aapp", host='0.0.0.0', port=7711)
