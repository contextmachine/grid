import json, gzip
import dataclasses
import os
import typing
import dotenv
dotenv.load_dotenv(os.getcwd())
from mmcore.services.redis.connect import get_cloud_connection
rconn = get_cloud_connection()
@dataclasses.dataclass
class StaticBuild:
    cut: list[int]
    cutted_tri:list
    names:list[str]
    centers:list[list[float]]
from src.cxm_props import PROJECT,BLOCK,ZONE
def create_name(project=PROJECT, block=BLOCK,zone=ZONE):
    return f"{project.lower()}:{block.lower()}:{zone.lower()}:build"


def set_static_build_data(key, data:typing.Union[StaticBuild, dict], conn=rconn):
    if isinstance(data, StaticBuild):
        data=dataclasses.asdict(data)
    return conn.set(key, gzip.compress(json.dumps(data).encode()))


def get_static_build_data(key, conn=rconn):
    return StaticBuild(**json.loads(gzip.decompress(conn.get(key)).decode()))

def build(path):
    with open(f"{path}/SW_names.json") as f:
        names = json.load(f)
    with open(f"{path}/SW_centers.json") as f:
        centers = json.load(f)
    with open(f"{path}/masks/cut.json") as f:
        cut = json.load(f)
    with gzip.open(f"{path}/SW_triangles_cutted.gz") as f:
        tri = json.load(f)
    return StaticBuild(cut=cut, centers=centers, cutted_tri=tri, names=names)

def alltasks(path, project=PROJECT, block=BLOCK,zone=ZONE, conn=rconn):
    print(create_name(project=project, block=block, zone=zone))
    return set_static_build_data(create_name(project=project, block=block, zone=zone), build(path=path), conn=conn)

