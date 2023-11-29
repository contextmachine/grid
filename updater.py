import time

import numpy as np
import requests
import rich
from scipy.spatial import KDTree
import os, dotenv

dotenv.load_dotenv('.env')
from src.preprocess.sveta_json import *

from mmcore.services.redis import sets

sets.rconn = rconn

from src.preprocess.sveta_json import SvetaJson


def to_object_form(jsn):
    jsn.prettify()
    return list(dict(zip(jsn.extract_keys(), vals)) for vals in zip(*jsn.extract_vals()))


def contour_server_request(url, names):
    build = requests.post(url, json=dict(names=names)).json()

    return build['mask'], build['shapes'], build['centers'], build['names'], build['props']


def contour_server_target_request(contours_url, grid_url):
    return contour_server_request(contours_url + '/contours-merged',
                                  names=requests.get(f'{grid_url}/zone-scopes').json())


def prettify(dt, buff=None):
    jsn = to_object_form(SvetaJson(dt))

    for item in jsn:
        pt = [float(item['x']), float(item['y']), float(item['z'])]

        buff.append(pt)
        ptr = len(buff) - 1

        item['center'] = ptr
    return jsn


def solve_kd(triangle_centers, new_data):
    buff = []
    dt = prettify(new_data, buff)
    arr = np.asarray(triangle_centers).reshape((len(triangle_centers), 3))

    vg = np.array(buff)
    # vg[..., 2] *= 0

    kd = KDTree(vg)

    dist, ix = kd.query(arr, distance_upper_bound=200)

    return kd, dist, ix, vg, arr, np.array(dt, dtype=object)[ix], True


def extract_groups(dat, names, target_keys):
    groups = dict()
    print(target_keys)
    for i, name in zip(dat, names):

        ss = tuple(i[k] for k in target_keys)
        if ss not in groups:
            groups[ss] = []
        groups[ss].append(name)

    return groups


def test_request(url, uuid, data):
    _url = f"{url}/props-update/{uuid}"
    # print(f"\nPOST {_url}")
    s = time.time()
    resp = requests.post(_url, json=data)
    mins, secs = divmod(time.time() - s, 60)
    if resp.status_code != 200:
        raise Exception(f'{(resp.status_code, resp.text, data)}')

    res = dict(status_code=resp.status_code, test=resp.text, min=mins, sec=secs)

    return res


def update_pipeline(grid_url, contours_url, new_data, uuid="mfb_sw_f_panels_masked_cut"):
    res = contour_server_target_request(contours_url, grid_url)
    kdres = solve_kd(res[2], new_data)
    l = list(kdres[5][0].keys())
    for i in ['x', 'y', 'z', 'center']:
        l.remove(i)
    grps = extract_groups(kdres[5], res[3], l)

    rich.print(len(grps))
    _l = len(grps)

    for j, (ks, grp) in enumerate(grps.items()):
        test_request(grid_url, uuid, dict(uuids=grp, props=dict(zip(l, ks))))
        print(f'{" " * (len(str(_l)) + 1)}{j}/{_l}', flush=True, end='\r')


if __name__ == '__main__':
    cs_url = 'https://viewer.contextmachine.online/cxm/api/v2/mfb_contour_server/sw'
    grid_url = 'https://viewer.contextmachine.online/cxm/api/v2/mfb_sw_l2_multiselect_test'
    with open("Types_SW_test.json", 'rb') as f:
        import json

        data = json.loads(f.read().decode('utf-8-sig'))

    res = update_pipeline(grid_url, cs_url, data)
