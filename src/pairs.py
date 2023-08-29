
def gen_stats_to_pairs(props_table):
        for name, arch_type, mask, cut in zip(props_table.columns['arch_type'].keys(),
                                         props_table.columns['arch_type'].values(),
                                         props_table.columns['projmask'].values(), props_table.columns['cut'].values()):
            yield {"name": name, 'arch_type': arch_type, 'projmask': mask, 'cut': cut}
from collections import Counter
def gen_pair_stats(props):
    dct = dict()
    for item in gen_stats_to_pairs(props_table=props):
        _name = item["name"].split("_")
        row, pair = _name[3], _name[4]
        if f'{row}_{pair}' not in dct:
            dct[f'{row}_{pair}'] = ""

        dct[f'{row}_{pair}'] += item["arch_type"]
    return dict(Counter(dct.values()))

def solve_pairs_stats(reflection, props):
    reflection["pairs_stats"] = gen_pair_stats( props= props)