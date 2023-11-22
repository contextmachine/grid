import dataclasses
import datetime
import os
import time
import typing

import httplib2
from googleapiclient.discovery import build

from oauth2client.service_account import ServiceAccountCredentials
import dotenv
import multiprocess

dotenv.load_dotenv(".env")

import json
from collections import Counter
from termcolor import colored, cprint


def get_service_sacc():
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds_service = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(os.getenv("GOOGLE_KF")),
                                                                     scopes).authorize(httplib2.Http())
    return build('sheets', 'v4', http=creds_service)


sheet = get_service_sacc().spreadsheets()


# import json


def resort(data, ks):
    yield ks
    for item in data:
        yield [item.get(k) for k in ks]


def pair_stats(data, key='arch_type', mask='cut', sep=" ", optional=None):
    dct = dict()
    iterkey = not isinstance(key, str)
    for item in data:
        spited_name = item["name"].split("_")
        projmask = item[mask]
        if projmask != 2:
            pair_name = spited_name[3] + "_" + spited_name[4]
            if pair_name not in dct:
                if optional is not None:
                    if item.get("Approved_zone"):

                        dct[pair_name] = f'{item.get("Approved_zone")}'
                    elif item.get("approved_zone"):
                        dct[pair_name] = f'{item.get("approved_zone")}'
                    else:
                        dct[pair_name] = ""
                else:
                    dct[pair_name] = ""

            if iterkey:
                for k in key:
                    dct[pair_name] += f'{sep}{item[k]}'
            else:
                dct[pair_name] += f'{sep}{item[key]}'

    return list(Counter(dct.values()).items())


def _pair_stats(data, key='arch_type', **kwargs):
    dct = dict()
    for item in data:
        spited_name = item["name"].split("_")
        projmask = item["projmask"]
        if projmask != 2:
            pairIndex = spited_name[3] + "_" + spited_name[4]
            if pairIndex not in dct:
                dct[pairIndex] = ""
            dct[pairIndex] += item[key]

    return list(Counter(dct.values()).items())


def approved_zone_stats(data, key='tag', mask='cut', sep=" ", optional=None):
    dct = dict()
    iterkey = not isinstance(key, str)
    for item in data:
        spited_name = item["name"].split("_")
        projmask = item[mask]
        if projmask != 2:
            pair_name = spited_name[3] + "_" + spited_name[4]
            if pair_name not in dct:
                if optional is not None:
                    dct[pair_name] = f'{item["Approved_zone"]}'
                else:
                    dct[pair_name] = ""

            if iterkey:
                for k in key:
                    dct[pair_name] += f'{sep}{item[k]}'

            else:
                dct[pair_name] += f'{sep}{item[key]}'
    return list(Counter(dct.values()).items())


# https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/update
def now(sep="T", domain='hours'):
    return datetime.datetime.now().isoformat(sep=sep, timespec=domain)


def logtime(): return f"[{colored(now(sep=' '), 'light_grey')}]"


def update_sheet(data, sheet_range, sheet_id=os.getenv("SHEET_ID")):
    return sheet.values().update(
        spreadsheetId=sheet_id,
        range=sheet_range,
        valueInputOption='RAW',
        body={'values': data}).execute()


_table_keys = ('name',
               'tag',
               'arch_type',
               'eng_type',
               'block',
               'zone',
               'cut',
               'pair_name',
               'pair_index',
               'mount',
               'mount_date',
               'area')


@dataclasses.dataclass
class GoogleSheetApiManagerWrite:
    sheet_range: str
    key: typing.Union[str, list[str]]
    mask: str = "cut"
    sep: str = " "

    @classmethod
    def from_dict(cls, dct):
        return cls(**dct)


import threading as th


@dataclasses.dataclass
class GoogleSheetApiManagerState:
    sheet_id: str
    main_sheet_range: str
    table_keys: list[str]
    writes: list[GoogleSheetApiManagerWrite]
    enable: bool = True

    @classmethod
    def from_dict(cls, dct):
        writes = dct.get('writes', [])
        if not len(writes) == 0:
            dct['writes'] = [GoogleSheetApiManagerWrite.from_dict(write) for write in writes]
        return cls(**dct)


@dataclasses.dataclass
class GoogleSheetApiManagerEnableEvent:
    value: bool


class GoogleSheetApiManager:
    def __init__(self, state: GoogleSheetApiManagerState = None, /,
                 sheet_id=None,
                 main_sheet_range="SW_L2_test!A1",
                 table_keys=_table_keys, writes=None, enable=True):
        if state:
            self.state = state
        else:
            if writes is None:
                writes = [GoogleSheetApiManagerWrite("SW_L2_pair_count_test!A2", "arch_type"),
                          GoogleSheetApiManagerWrite("SW_L2_pair_count_test!G2", "tag")]
            self.state = GoogleSheetApiManagerState(
                sheet_id=sheet_id,
                main_sheet_range=main_sheet_range,
                table_keys=table_keys,
                writes=writes,
                enable=enable

            )
            self._data = []

    def update_state(self, state: GoogleSheetApiManagerState):
        self.state = state

    def resort_table(self, data):
        return resort(data, self.state.table_keys)

    def update_sheet(self, data, sheet_range):
        if self.state.enable:
            return sheet.values().update(
                spreadsheetId=self.state.sheet_id,
                range=sheet_range,
                valueInputOption='RAW',
                body={'values': data}).execute()

    def update_all(self, data, sleep=0):

        _data = [dict(list(i) + [("name", i.index)]) for i in data]
        try:

            update_sheet(list(self.resort_table(_data)), sheet_range=self.state.main_sheet_range)
            wi = iter(self.state.writes)
            wr = next(wi)

            while True:
                try:

                    if wr.key == "tag":
                        dd = f"{wr.sheet_range.split('!')[0]}!K2"
                        update_sheet(pair_stats(_data, key=wr.key, mask=wr.mask, sep=wr.sep, optional="Approved_zone"),
                                     sheet_range=dd)
                        print(
                            f"{logtime()} {colored('complete approved_zone update !', 'green')}")
                        print(logtime(),
                              colored('OK', 'cyan', attrs=('bold',)),
                              colored(json.dumps({"status": "done", 'timestamp': now(),
                                                  "write": {'sheet_range': dd, 'key': wr.key, 'mask': wr.mask,
                                                            'sep': wr.sep}}), 'light_grey'))
                        break

                    wr = next(wi)

                except Exception as err:
                    print(f"{logtime()} {colored('break approved_zone update with internal err!', 'red')}")
                    dd = f"{wr.sheet_range.split('!')[0]}!K2"
                    print(logtime(),
                          colored('ERROR', 'red', attrs=('bold',)),
                          json.dumps({
                              "status": "fail",
                              'timestamp': now(),
                              "write": {
                                  'sheet_range': dd

                              },
                              "error": {
                                  'str': str(err),
                                  "repr": repr(err)
                              }
                          }, indent=2), 'light_grey')
                    break

            for write in self.state.writes:
                time.sleep(sleep)
                update_sheet(pair_stats(_data, key=write.key, mask=write.mask, sep=write.sep),
                             sheet_range=write.sheet_range)
                print(logtime(),
                      colored('OK', 'cyan', attrs=('bold',)),
                      colored(json.dumps({"status": "done", 'timestamp': now(), "write": dataclasses.asdict(write)}),
                              'light_grey'),

                      )
            print(f"{logtime()} {colored('writing to gsheet success!', 'green')}")


        except Exception as e:
            print(logtime(),
                  colored("ERROR", 'red', attrs="BOLD"),
                  colored(str(e), 'light_grey'))

            print(_data[0])

            return False

        return True


