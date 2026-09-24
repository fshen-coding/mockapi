import hashlib
import json
import os
from pathlib import Path
import sys

import psycopg
from psycopg import sql


def main():
    manifest = json.load(sys.stdin)
    result = {"tables": {}, "files": {}, "success": True}
    with psycopg.connect(os.environ["MOCKAPI_DATABASE_URL"]) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        for table_name, expected in manifest["tables"].items():
            statement = sql.SQL(
                "SELECT count(*), md5(string_agg(digest, '' ORDER BY digest)) "
                "FROM (SELECT md5(row_to_json(record)::text) AS digest "
                "FROM public.{} AS record) AS digests"
            ).format(sql.Identifier(table_name))
            count, digest = connection.execute(statement).fetchone()
            matched = {"rows": count, "digest": digest} == expected
            result["tables"][table_name] = {"rows": count, "matched": matched}
            result["success"] = result["success"] and matched
    data_root = Path("/app/web/data").resolve()
    for filename, expected in manifest.get("data_files", {}).items():
        target = (data_root / filename).resolve()
        if not target.is_relative_to(data_root):
            raise ValueError("Invalid data path")
        if not target.is_file():
            matched = False
        else:
            with target.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            matched = target.stat().st_size == expected["bytes"] and digest == expected["sha256"]
        result["files"][filename] = matched
        result["success"] = result["success"] and matched
    print(json.dumps(result, indent=2))
    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
