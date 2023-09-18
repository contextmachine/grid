import os


PROJECT=os.getenv("CXM_PROJECT")
BLOCK=os.getenv("CXM_BLOCK")
ZONE=os.getenv("CXM_ZONE")
DB_NAME=os.getenv("DB_NAME") if os.getenv("DB_NAME") is not None else 'tagdb_test'

