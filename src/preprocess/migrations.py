import json
import pickle


def migrate_tagdb_names(tgdb, migrate):
    changed_columns = dict()
    for column_name in tgdb.columns.keys():

        if tgdb.columns[column_name].__class__ == dict:
            new_col = dict()
            for k in tgdb.columns[column_name].keys():
                if k not in migrate.keys():
                    spl = k.split("_")
                    part = spl[-1]

                    new_col[migrate["_".join(spl[:-1])] + "_" + part] = tgdb.columns[column_name][k]
                else:
                    new_col[migrate[k]] = tgdb.columns[column_name][k]
            changed_columns[column_name] = new_col

    for column_name in list(changed_columns.keys()):
        tgdb.columns[column_name] = changed_columns[column_name]


def migrate_names(tagdb_path,tagdb_new_path, migrate_json_path):
    with open(migrate_json_path, 'r') as f:
        migrate = json.load(f)
    with open(tagdb_path, 'rb') as fp:
        tagdb = pickle.load(fp)
    migrate_tagdb_names(tagdb, migrate)
    with open(tagdb_new_path, 'wb') as ffp:
        pickle.dump(tagdb, ffp)
    return tagdb