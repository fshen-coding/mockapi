import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

import psycopg
from psycopg import sql


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--postgres-container", default="dpu-services-postgres-1")
    parser.add_argument("--app-container", default="dpu-services-mockapi-1")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    container = json.loads(
        subprocess.check_output(["docker", "inspect", args.app_container])
    )[0]
    environment = dict(item.split("=", 1) for item in container["Config"]["Env"])
    database_url = environment["MOCKAPI_DATABASE_URL"]
    postgres = json.loads(
        subprocess.check_output(["docker", "inspect", args.postgres_container])
    )[0]
    database_port = postgres["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"]
    manifest = {
        "snapshot_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "tables": {},
    }
    with psycopg.connect(database_url, host="127.0.0.1", port=database_port) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        snapshot = connection.execute("SELECT pg_export_snapshot()").fetchone()[0]
        tables = connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        ).fetchall()
        for (table_name,) in tables:
            statement = sql.SQL(
                "SELECT count(*), md5(string_agg(digest, '' ORDER BY digest)) "
                "FROM (SELECT md5(row_to_json(record)::text) AS digest "
                "FROM public.{} AS record) AS digests"
            ).format(sql.Identifier(table_name))
            count, digest = connection.execute(statement).fetchone()
            manifest["tables"][table_name] = {"rows": count, "digest": digest}
        with (output / "mockapi.dump").open("wb") as target:
            subprocess.run(
                [
                    "docker", "exec", args.postgres_container, "pg_dump",
                    "-U", "mockapi", "-d", "mockapi", "--format=custom",
                    "--no-owner", "--no-acl", f"--snapshot={snapshot}",
                ],
                stdout=target,
                check=True,
            )
    result = subprocess.run(
        ["docker", "exec", args.app_container, "tar", "czf", "-", "-C", "/app/web/data", "."],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.decode(errors="replace"))
    if result.returncode == 1:
        manifest["file_backup_warning"] = result.stderr.decode(errors="replace")
    (output / "data.tar.gz").write_bytes(result.stdout)
    with tarfile.open(output / "data.tar.gz") as archive:
        manifest["data_files"] = {
            member.name: {
                "bytes": member.size,
                "sha256": hashlib.sha256(archive.extractfile(member).read()).hexdigest(),
            }
            for member in archive.getmembers()
            if member.isfile()
        }
    manifest["dump_sha256"] = hashlib.file_digest(
        (output / "mockapi.dump").open("rb"), "sha256"
    ).hexdigest()
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({
        "snapshot_utc": manifest["snapshot_utc"],
        "tables": {name: value["rows"] for name, value in manifest["tables"].items()},
        "data_files": len(manifest["data_files"]),
        "dump_bytes": (output / "mockapi.dump").stat().st_size,
    }, indent=2))


if __name__ == "__main__":
    main()
