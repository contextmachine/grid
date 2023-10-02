import dataclasses
import os
import typing

import httplib2
from googleapiclient.discovery import build

from oauth2client.service_account import ServiceAccountCredentials
import dotenv

dotenv.load_dotenv(".env")

import json
from collections import Counter



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

def pair_stats(data, key='arch_type', mask='cut', sep=" "):
    dct = dict()
    iterkey = not isinstance(key, str)
    for item in data:
        spited_name = item["name"].split("_")
        projmask = item[mask]
        if projmask != 2:
            pair_name =  spited_name[3] + "_" + spited_name[4]
            if pair_name not in dct:
                dct[pair_name] = ""

            if iterkey:
                    for k in key:
                        dct[pair_name] += f'{sep}{item[k]}'
            else:
                    dct[pair_name] += f'{sep}{item[key]}'

    return list(Counter(dct.values()).items())

def _pair_stats(data, key='arch_type',**kwargs):
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



# https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/update


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
    key: typing.Union[str,list[str]]
    mask: str="cut"
    sep: str = " "

    @classmethod
    def from_dict(cls, dct):

        return cls(**dct)

@dataclasses.dataclass
class GoogleSheetApiManagerState:
    sheet_id: str
    main_sheet_range: str
    table_keys: list[str]
    writes: list[GoogleSheetApiManagerWrite]
    enable:bool=True

    @classmethod
    def from_dict(cls, dct):
        writes = dct.get('writes', [])
        if not len(writes) == 0:
            dct['writes'] = [GoogleSheetApiManagerWrite.from_dict(write) for write in writes]
        return cls(**dct)


@dataclasses.dataclass
class GoogleSheetApiManagerEnableEvent:
    value:bool
class GoogleSheetApiManager:
    def __init__(self, state: GoogleSheetApiManagerState=None, /,
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


    def update_all(self, data):
        import threading as th
        if self.state.enable:
            data_ = [dict(list(i) + [("name", i.index)]) for i in data]

            def proc():
                update_sheet(list(self.resort_table(data_)), sheet_range=self.state.main_sheet_range)
                for write in self.state.writes:
                    update_sheet(pair_stats(data_, key=write.key, mask=write.mask, sep=write.sep), sheet_range=write.sheet_range)
                print("google sheet updated!")

            thread = th.Thread(target=proc)
            thread.start()
