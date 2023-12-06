import dataclasses
import datetime
import gzip
import json
import pickle
import sys
import time
import threading as th
from collections import Counter
import typing

typing.TYPE_CHECKING = False
TYPE_CHECKING = False
import requests
import uvicorn
import os
import dotenv
import numpy as np
import pandas as pd
from earcut import earcut
from mmcore.base.geom import MeshData
from src.state import StateManager

dotenv.load_dotenv(dotenv_path=".env")
reflection = dict(recompute_repr3d=True, mask_index=dict(), cutted_childs=dict(), tris_rg=dict())
from src.props import TAGDB, colormap, rconn, cols, rmasks, sets, ColorMap, zone_scopes, gsheet_spec, PANEL_AREA, \
    MIN_CUT, zone_scopes_redis

from fastapi import FastAPI, UploadFile
from starlette.responses import FileResponse, HTMLResponse
from scipy.spatial import KDTree

from src.cxm_props import BLOCK, PROJECT, ZONE

from mmcore.geom.materials import ColorRGB
from mmcore.base import A, AGroup, AMesh

from mmcore.base.sharedstate import serve, debug_properties
from mmcore.base.registry import adict, idict

from mmcore.base import ALine, A, APoints, AGroup
import rich

rich.print(dict(os.environ))

print(TAGDB)
from src.pairs import solve_pairs_stats

update_flag = False

# This Api provides an extremely flexible way of updating data. You can pass any part of the parameter dictionary
# structure, the parameters will be updated recursively and only the part of the graph affected by the change
# will be recalculated.
reflection["tri_items"] = dict()
reflection["tris"] = list()
reflection['redis_cache'] = False

A.__gui_controls__.config.address = os.getenv("MMCORE_ADDRESS")
A.__gui_controls__.config.api_prefix = os.getenv("MMCORE_APPPREFIX")

from src.root_group import RootGroup, props_table, MaskedRootGroup
from src.gsh import GoogleSheetApiManager, GoogleSheetApiManagerEnableEvent, GoogleSheetApiManagerState, \
    GoogleSheetApiManagerWrite, logtime


# props_table = TagDB("mfb_sw_l2_panels")


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


def get_zone_scopes():
    return zone_scopes[ZONE]


servreq = zone_scopes_redis[ZONE]


def set_static_build_data(key, data, conn):
    return conn.set(key, gzip.decompress(json.dumps(data).encode()))


def get_static_build_data(key, conn):
    return json.loads(gzip.decompress(conn.get(key)).decode())


# build = json.loads(gzip.decompress(rconn.get(f"{PROJECT}:{BLOCK}:{ZONE}:build")).decode())
#
# cut, tri, tri_cen, tri_names = build['cut'], build['cutted_tri'], build['centers'], build['names']
CONTOUR_SERVER_URL = f'{os.getenv("CONTOUR_SERVER_URL")}/{BLOCK}/contours-merged'
print(servreq)
build = requests.post(CONTOUR_SERVER_URL, json=dict(names=servreq)).json()

cut, tri, tri_cen, tri_names, ar = build['mask'], build['shapes'], build['centers'], build['names'], build['props']
projmask = cut

itm2 = []

arr = np.asarray(tri_cen).reshape((len(tri_cen), 3))


def solve_kd(new_data):
    dt = list(prettify(new_data))
    reflection['data'] = dt

    vg = np.array(reflection["data_pts"])
    # vg[..., 2] *= 0

    kd = KDTree(vg)
    reflection["kd"] = kd
    dist, ix = reflection['kd'].query(arr, distance_upper_bound=200)

    reflection["ix"] = ix
    reflection["recompute_repr3d"] = True


class GridStateManager(StateManager):
    def __init__(self, procs, sleep_time=10):
        super().__init__(procs, sleep_time=sleep_time)

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)
        if (exc_type, exc_val, exc_tb) != (None, None, None):
            sys.exit(0)


from termcolor import colored, cprint


def now(sep="T", domain='hours'):
    return datetime.datetime.now().isoformat(sep=sep, timespec=domain)


def on_shutdown():
    print(f"[{colored(now(sep=' '), 'light_grey')}] {colored('... writing to redis', 'yellow')}")
    rconn.set(TAGDB, pickle.dumps(props_table))
    print(f"[{colored(now(sep=' '), 'light_grey')}] {colored(' writing to redis success!', 'green')}")
    return True


def create_redis_snapshot():
    print(f"[{colored(now(sep=' '), 'light_grey')}] {colored('... writing snapshot to redis', 'yellow')}")
    snaptime = now(sep='T')
    k = f"{TAGDB}_snapshot:{snaptime}"
    rconn.set(k, gzip.compress(pickle.dumps(props_table), compresslevel=9))

    print(f"[{colored(now(sep=' '), 'light_grey')}] {colored('writing snapshot to redis success!', 'green')}")
    print(f"[{colored(now(sep=' '), 'light_grey')}] {colored(k, 'cyan')}")


google_sheet_manager = GoogleSheetApiManager(GoogleSheetApiManagerState.from_dict(dict(gsheet_spec[BLOCK][ZONE])))


def gsheet_updater(arg=(40, 10)):
    sleep, retry = arg[0], arg[1]
    print(f"[{colored(now(sep=' '), 'light_grey')}] {colored('... writing to gsheet', 'yellow')}")

    res = google_sheet_manager.update_all(reflection['tris'])
    calls = 1

    def retry_caller(result):
        nonlocal retry, calls
        if not result:
            print(logtime(), colored("ERROR", 'red', attrs=("bold",)))
            for i in range(sleep):
                time.sleep(1)
                print(colored(f"retry ({calls}) after {sleep - i} secs.", 'light_grey'), flush=True, end="\r")
            calls += 1
            retry -= 1
            if retry > 0:
                retry_caller(google_sheet_manager.update_all(reflection['tris']))

    retry_caller(res)


class GoogleSupportRootGroup(MaskedRootGroup):
    def make_cache(self):
        global appmanager
        super().make_cache()
        appmanager.update()
        # snapshot_time=datetime.datetime.now().isoformat(
        #    sep=" ", timespec='hours')
        # if reflection['redis_cache']:
        #    on_shutdown()
        # rconn.set(
        #    f"{TAGDB}_snapshot:{snapshot_time}", gzip.compress(pickle.dumps(props_table), compresslevel=9))

        # print(f"Save tagDB snapshot at {snapshot_time}")
        # on_shutdown()
        # sys.getsizeof(reflection)
        # sys.getsizeof(google_sheet_manager)
        # google_sheet_manager.update_all(reflection["tris"])


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
    def _material(self, v):
        print("ignore set material")
        pass


@dataclasses.dataclass(slots=True)
class RedisDumpChangeEvent:
    value: bool = False


class CompoundPanel(AGroup):
    '''@property
    def properties(self):
        return props_table[self.uuid]
    @properties.setter
    def properties(self, props: dict):
        props_table[self.uuid].set(dict(props))'''


def solve_triangles(triangles, names, colors, mask, areas, area_exp=lambda val: round(val * 1e-6, 4),
                    min_cut_exp=lambda val: round(val * 1e-6, 4) < MIN_CUT):
    reflection["tri_items"] = dict()
    reflection["tris"] = []
    for i, j in enumerate(reflection['ix']):
        try:
            reflection["data"][j]
        except IndexError:
            # print(False)
            j = j - 1
        tag = f'{reflection["data"][j]["arch_type"]}-{reflection["data"][j]["eng_type"]}'
        if tag not in colors:
            colors[tag] = np.random.randint(30, 230, 3).tolist()
        ppp = triangles[i]

        uuid = names[i].replace(":", "_")
        splitted_uuid = uuid.split("_")
        pair_name = splitted_uuid[3] + "_" + splitted_uuid[4]

        reflection["mask_index"][uuid] = i

        # props_table[uuid]["tag"] = tag
        for k, v in reflection['data'][j].items():
            if k in props_table.columns.keys():
                column = props_table.columns[k]
                if uuid not in column.keys():
                    props_table.set_column_item(k, uuid, v)
            else:
                props_table.set_column_item(k, uuid, v)
                # column[uuid] = v

        props_table[uuid]["cut"] = mask[i]
        props_table[uuid]["cut_mask"] = mask[i]
        props_table[uuid]["projmask"] = mask[i]

        # ADD PAIRS!
        props_table[uuid]["pair_name"] = pair_name
        props_table[uuid]["pair_index"] = uuid[-1]
        props_table[uuid]["area"] = area_exp(areas[i][0]['area'])
        props_table[uuid]["min_cut"] = min_cut_exp(areas[i][0]['area'])

        # ADD PAIRS!

        if uuid not in reflection["tri_items"].keys():

            if len(ppp) > 1:

                pan = CompoundPanel(uuid=uuid, name=uuid,
                                    _endpoint="triangle_handle/" + uuid,
                                    )

                pan._endpoint = "triangle_handle/" + uuid

                for k, pts in enumerate(ppp):

                    part_uuid = uuid + f"_{k + 1}"

                    for key, v in reflection['data'][j].items():
                        if key in props_table.columns.keys():
                            column = props_table.columns[key]
                            if part_uuid not in column.keys():
                                props_table.set_column_item(key, part_uuid, v)
                        else:
                            props_table.set_column_item(key, part_uuid, v)
                    props_table[part_uuid]['cut'] = 1

                    try:

                        props_table.columns["pair_name"][uuid + f"_{k + 1}"] = pair_name
                        props_table.columns["pair_index"][uuid + f"_{k + 1}"] = uuid[-1]
                        props_table.columns["area"][uuid + f"_{k + 1}"] = area_exp(areas[i][k]['area'])
                        props_table.columns["min_cut"][uuid + f"_{k + 1}"] = min_cut_exp(areas[i][k]['area'])
                    except:

                        props_table.columns["pair_name"][uuid + f"_{k + 1}"] = pair_name
                        props_table.columns["pair_index"][uuid + f"_{k + 1}"] = uuid[-1]
                        props_table.columns["area"][uuid + f"_{k + 1}"] = area_exp(areas[i][k]['area'])
                        props_table.columns["min_cut"][uuid + f"_{k + 1}"] = min_cut_exp(areas[i][k]['area'])

                    res = earcut.flatten([pts])
                    _tess = earcut.earcut(res['vertices'], res['holes'], res['dimensions'])

                    geom = MeshData(vertices=pts, indices=np.array(_tess, dtype=int).reshape(
                        (len(_tess) // 3, 3)).tolist()).create_buffer()
                    panel = PanelMesh(uuid=uuid + f"_{k + 1}", name=uuid + f"_{k + 1}", geometry=geom,
                                      _endpoint="triangle_handle/" + uuid + f"_{k + 1}")

                    panel.controls = props_table[uuid + f"_{k + 1}"]
                    panel._endpoint = "triangle_handle/" + uuid + f"_{k + 1}"
                    reflection["tris"].append(props_table[uuid + f"_{k + 1}"])

                    pan.add(panel)

                    reflection["tri_items"][part_uuid] = panel
            else:
                # mask_db.index_map.append(i)
                # prt = Part(i, mask_db)
                # prt.set('parent_uuid', uuid)
                # prt.set('self_uuid', uuid)
                # props_table["name"][uuid] = uuid
                res = earcut.flatten(ppp)  # trii.triangulate()
                _tess = earcut.earcut(res['vertices'], res['holes'], res['dimensions'])
                # print(ppp)
                geom = MeshData(vertices=ppp, indices=np.array(_tess, dtype=int).reshape(
                    (len(_tess) // 3, 3)).tolist()).create_buffer()

                # trii = Triangle(*ppp[0])

                pan = PanelMesh(uuid=uuid, name=uuid, geometry=geom,
                                _endpoint="triangle_handle/" + uuid)

                pan.controls = props_table[uuid]
                pan._endpoint = "triangle_handle/" + uuid
                reflection["tri_items"][uuid] = pan

                reflection["tris"].append(props_table[uuid])

    if f"{PROJECT}_{BLOCK}_{ZONE}_panels" not in idict.keys():
        grp = RootGroup(uuid=f"{PROJECT}_{BLOCK}_{ZONE}_panels", name=f"{BLOCK} {ZONE} panels".upper())
        grp.scale(0.001, 0.001, 0.001)

    idict[f"{PROJECT}_{BLOCK}_{ZONE}_panels"]["__children__"] = set(reflection['tri_items'].keys())


def reload_datapoints(addr=f"api:mmcore:runtime:{PROJECT}:{BLOCK}:{ZONE}:datapoints"):
    _dt = rconn.get(addr)
    if _dt is not None:
        if isinstance(_dt, bytes):
            _dt = _dt.decode()
        solve_kd(json.loads(_dt))


@serve.app.get("/table")
def stats1():
    tab = pd.DataFrame([dict(list(i) + [("name", i.index)]) for i in reflection["tris"]])
    tab.to_csv("table.csv")
    return FileResponse("table.csv", filename="table.csv", media_type="application/csv")


@serve.app.post("/masks/add/{name}")
async def mask_handle(name, data: dict):
    # mm = dict(cmr.todict()['masks'])
    rmasks[name] = data["masks"]
    props_table.set_column(name, dict(zip(props_table.get_column("tag").keys(), data['masks'])))
    # mm[name] = data["state"]

    # cmr(masks=mm)
    # return mm


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
            # cmr()

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
    return [dict(list(i) + [("name", i.index)]) for i in reflection["tris"]]


@serve.app.get("/stats/pairs")
async def stats_pairs():
    return reflection["pairs_stats"]


@serve.app.get("/props_table")
def pt():
    with open("props_table.pkl", 'wb') as f:
        pickle.dump(props_table, f)
    return FileResponse(path=f"props_table.pkl", filename=f"props_table_{PROJECT}_{BLOCK}_{ZONE}.pkl")


def rule(dct):
    def wrap(obj):
        if len(dct) == 0:
            return False
        return all([obj[k] == dct[k] for k in dct.keys()])

    return wrap


def stats_aggregate(dat, keys, mask=lambda x: x['cut'] != 2, sep=" "):
    def gen():
        for item in filter(mask, dat):
            yield sep.join(f'{item[key]}' for key in keys)

    return dict(Counter(gen()))


@serve.app.post("/where")
def where_query(data: dict):
    rul = rule(data)
    return [dict(list(_i) + [("name", _i.index)]) for _i in list(filter(rul, reflection["tris"]))]


@serve.app.post("/where/{uid}")
async def where_obj(uid: str, data: dict):
    adict.get(uid).rule_data = data

    return data


@serve.app.get("/where/{uid}")
async def where_objget(uid: str):
    return adict.get(uid).rule_data


@dataclasses.dataclass
class AggregateQuery:
    keys: list[str]
    sep: str = " "


@serve.app.post("/aggregate")
async def aggregate(data: AggregateQuery):
    return stats_aggregate([dict(list(_i) + [("name", _i.index)]) for _i in reflection["tris"]],
                           keys=data.keys,
                           sep=data.sep)


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


@serve.app.get("/update-contours")
def upd_cont():

    zs=zone_scopes_redis[ZONE]
    print(get_zone_scopes(),zs)
    build = requests.post(CONTOUR_SERVER_URL, json=dict(names=zs)).json()

    cut, tri, tri_cen, tri_names, ar = build['mask'], build['shapes'], build['centers'], build['names'], build['props']
    solve_triangles(tri, tri_names, cols, cut, ar)
    adict[f"{PROJECT}_{BLOCK}_{ZONE}_panels_masked_cut"].recompute_mask()

    return "Ok"


@serve.app.get("/update-types")
def upd_types():
    print(get_zone_scopes())
    build = requests.post(CONTOUR_SERVER_URL, json=dict(names=servreq)).json()

    cut, tri, tri_cen, tri_names, ar = build['mask'], build['shapes'], build['centers'], build['names'], build['props']
    reload_datapoints()
    solve_triangles(tri, tri_names, cols, cut, ar)
    adict[f"{PROJECT}_{BLOCK}_{ZONE}_panels_masked_cut"].recompute_mask()
    return "Ok"


@serve.app.post("/zone-scopes")
def update_zone_scopes(data: list[str]):
    zone_scopes[ZONE] = data
    zone_scopes_redis[ZONE] = data
    for d in data:
        if d not in servreq:
            servreq.append(d)

    build = requests.post(CONTOUR_SERVER_URL, json=dict(names= zone_scopes_redis[ZONE])).json()

    cut, tri, tri_cen, tri_names, ar = build['mask'], build['shapes'], build['centers'], build['names'], build['props']
    solve_triangles(tri, tri_names, cols, cut, ar)
    adict[f"{PROJECT}_{BLOCK}_{ZONE}_panels_masked_cut"].recompute_mask()

    return  zone_scopes_redis[ZONE]


@serve.app.get("/zone-scopes")
def get_zone_scopes():
    return zone_scopes_redis[ZONE]

@serve.app.post("/zone-scopes/add")
def add_zone_scopes(value: list[str]):
    zs = zone_scopes_redis[ZONE]
    if not isinstance(value,str):

        for i in value:
            if i not in zs:
                zs.append(i)
        zone_scopes_redis[ZONE]=zs
    else:
        if value not in zs:
            zs.append(value)
        zone_scopes_redis[ZONE] = zs
        return zone_scopes_redis[ZONE]

@serve.app.post("/redis_cache")
async def redis_dumps(data: RedisDumpChangeEvent):
    reflection['redis_cache'] = data.value
    return reflection['redis_cache']


@serve.app.get("/redis_cache")
async def redis_cache_get():
    return reflection['redis_cache']


@serve.app.get("/gsheet")
async def get_gsheet_state():
    return google_sheet_manager.state


@serve.app.post("/gsheet")
async def post_gsheet_state(data: GoogleSheetApiManagerState):
    google_sheet_manager.update_state(data)
    gsheet_spec[BLOCK][ZONE] = dataclasses.asdict(google_sheet_manager.state)
    google_sheet_manager.update_all(reflection["tris"])
    return google_sheet_manager.state




@serve.app.post("/gsheet/enabled")
async def post_gsheet_enabled(data: GoogleSheetApiManagerEnableEvent):
    google_sheet_manager.state.enable = data.value
    gsheet_spec[BLOCK][ZONE] = dataclasses.asdict(google_sheet_manager.state)
    google_sheet_manager.update_all(reflection["tris"])
    return GoogleSheetApiManagerEnableEvent(value=google_sheet_manager.state.enable)


@serve.app.post("/gsheet/writes/add")
async def add_gsheet_writes(data: list[GoogleSheetApiManagerWrite]):
    google_sheet_manager.state.writes.extend(data)
    gsheet_spec[BLOCK][ZONE] = dataclasses.asdict(google_sheet_manager.state)
    google_sheet_manager.update_all(reflection["tris"])
    return google_sheet_manager.state.writes


@serve.app.post("/gsheet/writes")
async def post_gsheet_writes(data: list[GoogleSheetApiManagerWrite]):
    google_sheet_manager.state.writes = data
    gsheet_spec[BLOCK][ZONE] = dataclasses.asdict(google_sheet_manager.state)
    google_sheet_manager.update_all(reflection["tris"])
    return google_sheet_manager.state.writes


@serve.app.get("/gsheet/update_data_in_google_sheet_table")
async def gsheet_update():
    if google_sheet_manager.state.enable:
        try:
            google_sheet_manager.update_all(reflection["tris"])
            return {"success": True, "reason": None}
        except Exception as err:
            return {"success": False, "reason": {"exception": repr(err)}}
    else:
        return {"success": False, "reason": {"state": {
            "enable": False
        }}}

@serve.app.get("/gsheet/disable")
def disable_gsheet():
    appmanager.pause(0)
    return {'paused': list(appmanager.paused), 'running': list(set(range(len(appmanager.procs)))-appmanager.paused)}
@serve.app.get("/gsheet/shedule")
def shedule_gsheet():
    appmanager.manual_runs.add(0)
    return {'paused': list(appmanager.paused), 'running': list(set(range(len(appmanager.procs)))-appmanager.paused)}

@serve.app.get("/gsheet/enable")
def enable_gsheet():
    appmanager.resume(0)
    return {'paused': list(appmanager.paused), 'running': list(set(range(len(appmanager.procs)))-appmanager.paused)}

if os.getenv("TEST_DEPLOYMENT") is None:
    aapp = FastAPI(on_shutdown=[on_shutdown])
elif os.getenv('DUMP_TAGDB') == "1":
    aapp = FastAPI(on_shutdown=[on_shutdown])
else:
    aapp = FastAPI()
aapp.mount(os.getenv("MMCORE_APPPREFIX"), serve.app)

# import threading as th
# def app_thread():
#    uvicorn.run("main:aapp", host='0.0.0.0', port=7711)
debug_properties['target'] = f"{PROJECT}_{BLOCK}_{ZONE}_panels_masked_cut"
# app_th = th.Thread(target=app_thread)
# init()
# app_th.start()
# ttg = TrisRGroup(uuid="query_object", name="query_object", _endpoint="where/query_object", rule_data={"cut": 0})
# ttg.scale(0.001, 0.001, 0.001)

if __name__ == "__main__":

    with GridStateManager((gsheet_updater, on_shutdown, create_redis_snapshot), sleep_time=25) as appmanager:

        def init():
            _dt = rconn.get(f"api:mmcore:runtime:{PROJECT}:{BLOCK}:{ZONE}:datapoints")
            if _dt is not None:
                if isinstance(_dt, bytes):
                    _dt = _dt.decode()
                solve_kd(json.loads(_dt))

            solve_triangles(tri, tri_names, cols, cut, ar)

            pgrp = GoogleSupportRootGroup(uuid=f"{PROJECT}_{BLOCK}_{ZONE}_panels_masked_cut",
                                          name=f"{BLOCK} {ZONE}".upper(),
                                          owner_uuid=f"{PROJECT}_{BLOCK}_{ZONE}_panels")
            # pgrp.recompute_mask()
            pgrp.add_entries_support()
            pgrp.add_props_update_support()

            pgrp.scale(0.001, 0.001, 0.001)
            # solve_pairs_stats(reflection=reflection,props=props_table)
            print(pgrp.uuid)
            pgrp.mask_name = "cut"


        init()
        print(os.getenv("MMCORE_ADDRESS") + "/" + os.getenv("MMCORE_APPPREFIX"))

        uvicorn.run("main:aapp", host='0.0.0.0', port=7711)
