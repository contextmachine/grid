import sys

try:
    import requests
    import rich
except ImportError:
    import subprocess as sp
    proc=sp.Popen("pip install requests rich".split(" "))
    proc.communicate(

    )
import requests



# language=GraphQl
insert_query="""

mutation Insert($data: jsonb = "",$name: String = null, ) {
  insert_threejs_blobs_one(object: {data: $data, name:$name}) {
    id
    name
    update_at
  }
}

"""
# language=GraphQl
update_query="""
mutation Update($data: jsonb = "", $id: Int = 1) {
  update_threejs_blobs_by_pk(pk_columns: {id: $id}, _set: {data: $data}) {
    id
    name
    update_at
  }
}

"""

HASURA="http://51.250.47.166:8080/v1/graphql"
HEADERS={
    "x-hasura-admin-secret":"mysecretkey"
}
def req(query, payload):

    resp=requests.post(HASURA, json={
        "query":query,
        "variables":payload
    }, headers=HEADERS)
    try:
        return resp.json()
    except Exception as err:
        raise Exception(f"Response {resp.text} with exception {err}")

import rich
if __name__=="__main__":

    import json
    args={
        "update":update_query,
        "insert":insert_query
          }
    if len(sys.argv[1:])<3:
        h,= sys.argv[1:]
        if h=="-h" or h=="--help":

            rich.print("#TODO: help")
    else:
        arg, name_or_id, fp = sys.argv[1:]

        with open(fp,"r") as f:

            payload = {"data": json.load(f)}

        if arg=="update":
            payload["id"]=name_or_id
        else:
            payload["name"] = name_or_id

        rich.print("\n\nresponse:\n")
        rich.print_json(json.dumps(req(args[arg], payload)))
