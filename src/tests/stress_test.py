import datetime
import json
import time

import numpy as np

from collections import Counter
import requests
import rich

from termcolor import colored
def bool_change_gen(curval):
    return not curval


import copy


def enum_change_gen(available):
    def change_gen(curval):
        av = list(copy.copy(available))
        av.remove(curval)

        return av[int(np.random.randint(len(av)))]

    return change_gen


def extract_names(data):
    for d in data:
        if d['mask'] != 2:
            yield d['name']
def extract_key(data, key):
    for d in data:
        if d['cut'] != 2:
            yield d[key]


def stress_test_data(count, data, keys):
    *names, = extract_key(data, 'name')

    pull = np.random.randint(0, len(names) - 1, size=count)
    test_data = []
    for i in pull:
        dt = data[i]

        props = dict()
        request = dict(uuids=[dt['name']], props=props)
        for k, f in keys.items():
            if bool(np.random.randint(2)):
                props[k] = f(dt[k])
        if len(props) > 0:
            test_data.append(request)
    return test_data
import multiprocess as mp
import multiprocessing as mpp
URL="https://viewer.contextmachine.online/cxm/api/v2/mfb_sw_l2_multiselect_test"
TESTUUID="mfb_sw_l2_panels_masked_cut"
log=[]
def test_request(data):
    _url=f"{URL}/props-update/{TESTUUID}"
    print(f"\nPOST {_url}")
    rich.print_json(json.dumps(data))
    s=time.time()
    resp=requests.post(_url,json=data)
    mins,secs=divmod(time.time()-s,60)

    res=dict(status_code=resp.status_code, test=resp.text, min=mins, sec=secs)
    log.append(res)

    print(json.dumps(res))
    return res

def test_stress(count=4):
    resp = requests.get(f"{URL}/stats")
    stats = resp.json()

    *arch_type_vals, = extract_key(stats, 'arch_type')
    atv = list(Counter(arch_type_vals).keys())
    atv.remove('3')
    arch_type_gen = enum_change_gen(atv)

    sdt = stress_test_data(count, stats, {'arch_type': arch_type_gen, 'mount': bool_change_gen, 'stub': bool_change_gen})

    return sdt

if __name__ == '__main__':
    COUNT=16
    data=test_stress(count=COUNT)
    exc=None
    rich.print(f"\nGenerate {COUNT} test items:\n\n")
    rich.print_json(json.dumps(data))
    rich.print(f"\nStart Tests:\n\n")
    try:

        with mp.Pool(4) as p:
            res=p.map(test_request, data)
    except Exception as err:
        exc=repr(err)
    dt=datetime.datetime.now().isoformat()
    if exc:
        summary={
            "timestamp": dt,
            "tests": data,
            "results":log,
            "exception": exc,
            "success": False
        }
    else:
        summary={
        "timestamp": dt,
        "tests": data,
        "results": list(res),
        "exception": exc,
        "success":True

    }

    with open(f"stress_test_result_{dt.replace(':', '-').split('.')[0]}.json" ,"w") as f:
            json.dump(summary, f, indent=2)
    resp=requests.get(url=URL+'/stats')
    if resp.status_code==200:
        print(colored("Test passed!","cyan",attrs=('bold',)))
    else:
        print(colored("Failed!", "red",attrs=('bold',)))
        print(resp.text)