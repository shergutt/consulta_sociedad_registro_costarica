#!/usr/bin/env python3
"""Migrate data from SQLite v1 (per-user) to PostgreSQL v2 (person-shared).

Strategy:
  1. Truncate all v2 tables in reverse FK order.
  2. Reinsert users + sessions (FKs unchanged).
  3. For each person v1: insert into v2.persons.
  4. For each analysis_run v1: keep only the latest per person (MAX(ran_at)).
     Older runs are discarded (per user decision).
  5. Reinsert fincas / movable_assets as children of persons, point to the
     kept query_runs.
  6. Reinsert query_outputs, finca_query_outputs, alerts, source_files.
  7. Populate person_queries (auditing) from the kept runs.
"""
import os
import sqlite3
import sys
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values

ROOT = Path(__file__).parent.parent
SQLITE_PATH = ROOT / "rnp_personas.sqlite"
PG_URL = os.environ.get("DATABASE_URL")
if not PG_URL:
    raise SystemExit(
        "DATABASE_URL no está definido. Exportalo o configurá backend/.env "
        "antes de correr la migración desde SQLite."
    )


def _parse_dt(value):
    if not value:
        return None
    s = str(value).replace("Z", "+00:00")
    from datetime import datetime
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")


def migrate():
    if not SQLITE_PATH.exists():
        print(f"SQLite file not found: {SQLITE_PATH}")
        sys.exit(1)

    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
    sqlite_conn.row_factory = sqlite3.Row
    pg = psycopg2.connect(PG_URL)
    pg.autocommit = False
    cur = pg.cursor()

    try:
        print("Clearing PostgreSQL v2 data...")
        cur.execute("TRUNCATE finca_query_outputs, alerts, source_files, query_outputs, fincas, movable_assets, query_runs, person_queries, sessions, users, persons CASCADE")
        pg.commit()

        # --- users + sessions ---
        users_rows = sqlite_conn.execute("SELECT id, username, password_hash, role, created_at, updated_at FROM users").fetchall()
        if users_rows:
            users_data = [tuple(r) for r in users_rows]
            execute_values(cur, """
                INSERT INTO users (id, username, password_hash, role, created_at, updated_at)
                VALUES %s
            """, users_data, template="(%s, %s, %s, %s, %s, %s)")
        print(f"  users: {len(users_rows)} rows migrated")

        user_ids = {r["id"] for r in users_rows}
        sessions_rows = sqlite_conn.execute("SELECT token, user_id, created_at, expires_at FROM sessions").fetchall()
        valid_sessions = [r for r in sessions_rows if r["user_id"] in user_ids]
        if valid_sessions:
            execute_values(cur, """
                INSERT INTO sessions (token, user_id, created_at, expires_at)
                VALUES %s
            """, [tuple(r) for r in valid_sessions])
        print(f"  sessions: {len(valid_sessions)} rows migrated (filtered {len(sessions_rows) - len(valid_sessions)} orphan)")

        # --- persons ---
        persons_rows = sqlite_conn.execute(
            "SELECT id, cedula, nombre, first_name, latest_folder_path, created_at, updated_at FROM persons"
        ).fetchall()
        if persons_rows:
            execute_values(cur, """
                INSERT INTO persons (id, cedula, nombre, first_name, latest_folder_path, created_at, updated_at)
                VALUES %s
            """, [tuple(r) for r in persons_rows])
        print(f"  persons: {len(persons_rows)} rows migrated")

        # --- latest run per person ---
        latest_run_ids = [
            r[0] for r in sqlite_conn.execute(
                "SELECT id FROM analysis_runs ar1 "
                "WHERE ran_at = (SELECT MAX(ran_at) FROM analysis_runs ar2 WHERE ar2.person_id = ar1.person_id)"
            ).fetchall()
        ]
        print(f"  analysis_runs v1: {len(latest_run_ids)} kept (latest per person)")

        # --- query_runs + person_queries ---
        if latest_run_ids:
            placeholders = ",".join("?" * len(latest_run_ids))
            runs_rows = sqlite_conn.execute(
                f"SELECT id, person_id, user_id, folder_path, report_path, report_markdown, "
                f"finca_count, alert_count, output_counts_json, ran_at, created_at "
                f"FROM analysis_runs WHERE id IN ({placeholders})", latest_run_ids
            ).fetchall()
            execute_values(cur, """
                INSERT INTO query_runs (id, person_id, triggered_by_user_id, folder_path,
                    report_path, report_markdown, finca_count, alert_count,
                    output_counts_json, ran_at, created_at)
                VALUES %s
            """, [tuple(r) for r in runs_rows])
            print(f"  query_runs: {len(runs_rows)} rows migrated")

            pq_rows = [(r["person_id"], r["user_id"], r["ran_at"]) for r in runs_rows]
            execute_values(cur, """
                INSERT INTO person_queries (person_id, user_id, queried_at)
                VALUES %s
            """, pq_rows)
            print(f"  person_queries: {len(pq_rows)} rows migrated")

        # --- fincas (re-attach to person, keep same run_id) ---
        if latest_run_ids:
            placeholders = ",".join("?" * len(latest_run_ids))
            fincas_rows = sqlite_conn.execute(
                f"SELECT id, run_id, index_no, provincia, provincia_codigo, numero, derecho, "
                f"duplicado, horizontal, matricula, naturaleza, ubicacion, zona_catastrada, "
                f"medida, plano, antecedentes, identificador_predial, valor_fiscal_text, "
                f"valor_fiscal_num, propietario, anotaciones, gravamenes, resumen_json, "
                f"detalle_json, texto, source_json, source_txt, source_html, created_at "
                f"FROM fincas WHERE run_id IN ({placeholders})", latest_run_ids
            ).fetchall()
            if fincas_rows:
                run_id_map = {r["id"]: r["id"] for r in runs_rows}  # IDs preserved
                person_map = {r["id"]: r["person_id"] for r in runs_rows}
                fincas_v2 = []
                for r in fincas_rows:
                    fincas_v2.append((
                        r["id"], person_map[r["run_id"]], r["run_id"], r["index_no"],
                        r["provincia"], r["provincia_codigo"], r["numero"], r["derecho"],
                        r["duplicado"], r["horizontal"], r["matricula"], r["naturaleza"],
                        r["ubicacion"], r["zona_catastrada"], r["medida"], r["plano"],
                        r["antecedentes"], r["identificador_predial"], r["valor_fiscal_text"],
                        r["valor_fiscal_num"], r["propietario"], r["anotaciones"],
                        r["gravamenes"], r["resumen_json"], r["detalle_json"], r["texto"],
                        r["source_json"], r["source_txt"], r["source_html"],
                        r["created_at"], r["created_at"],
                    ))
                execute_values(cur, """
                    INSERT INTO fincas (id, persona_id, query_run_id, index_no, provincia,
                        provincia_codigo, numero, derecho, duplicado, horizontal, matricula,
                        naturaleza, ubicacion, zona_catastrada, medida, plano, antecedentes,
                        identificador_predial, valor_fiscal_text, valor_fiscal_num,
                        propietario, anotaciones, gravamenes, resumen_json, detalle_json,
                        texto, source_json, source_txt, source_html, created_at, updated_at)
                    VALUES %s
                """, fincas_v2)
            print(f"  fincas: {len(fincas_rows)} rows migrated")

            # --- movable_assets ---
            ma_rows = sqlite_conn.execute(
                f"SELECT id, run_id, index_no, asset_type, identificacion, nombre, tipo, "
                f"numero, placa, matricula, marca, modelo, year, color, serie, vin, motor, "
                f"chasis, propietario, cedula_propietario, estado, anotaciones, gravamenes, "
                f"resumen_json, detalle_json, texto, source_json, source_txt, source_html, "
                f"created_at FROM movable_assets WHERE run_id IN ({placeholders})", latest_run_ids
            ).fetchall()
            if ma_rows:
                ma_v2 = []
                for r in ma_rows:
                    ma_v2.append((
                        r["id"], person_map[r["run_id"]], r["run_id"], r["index_no"],
                        r["asset_type"], r["identificacion"], r["nombre"], r["tipo"],
                        r["numero"], r["placa"], r["matricula"], r["marca"], r["modelo"],
                        r["year"], r["color"], r["serie"], r["vin"], r["motor"], r["chasis"],
                        r["propietario"], r["cedula_propietario"], r["estado"], r["anotaciones"],
                        r["gravamenes"], r["resumen_json"], r["detalle_json"], r["texto"],
                        r["source_json"], r["source_txt"], r["source_html"],
                        r["created_at"], r["created_at"],
                    ))
                execute_values(cur, """
                    INSERT INTO movable_assets (id, persona_id, query_run_id, index_no,
                        asset_type, identificacion, nombre, tipo, numero, placa, matricula,
                        marca, modelo, year, color, serie, vin, motor, chasis, propietario,
                        cedula_propietario, estado, anotaciones, gravamenes, resumen_json,
                        detalle_json, texto, source_json, source_txt, source_html,
                        created_at, updated_at)
                    VALUES %s
                """, ma_v2)
            print(f"  movable_assets: {len(ma_rows)} rows migrated")

            # --- query_outputs ---
            qo_rows = sqlite_conn.execute(
                f"SELECT id, run_id, query_type, lookup_key, consulta, entrada_json, "
                f"origen_json, payload_json, texto, source_json, source_txt, source_html, "
                f"created_at FROM query_outputs WHERE run_id IN ({placeholders})", latest_run_ids
            ).fetchall()
            if qo_rows:
                qo_v2 = [tuple(r) for r in qo_rows]
                execute_values(cur, """
                    INSERT INTO query_outputs (id, query_run_id, query_type, lookup_key,
                        consulta, entrada_json, origen_json, payload_json, texto,
                        source_json, source_txt, source_html, created_at)
                    VALUES %s
                """, qo_v2)
            print(f"  query_outputs: {len(qo_rows)} rows migrated")

            # --- finca_query_outputs ---
            fqo_rows = sqlite_conn.execute(
                f"SELECT finca_id, query_output_id, relation FROM finca_query_outputs "
                f"WHERE finca_id IN (SELECT id FROM fincas WHERE run_id IN ({placeholders}))",
                latest_run_ids
            ).fetchall()
            if fqo_rows:
                execute_values(cur, """
                    INSERT INTO finca_query_outputs (finca_id, query_output_id, relation)
                    VALUES %s
                """, [tuple(r) for r in fqo_rows])
            print(f"  finca_query_outputs: {len(fqo_rows)} rows migrated")

            # --- alerts ---
            alerts_rows = sqlite_conn.execute(
                f"SELECT id, run_id, finca_id, severity, label, message, source, created_at "
                f"FROM alerts WHERE run_id IN ({placeholders})", latest_run_ids
            ).fetchall()
            if alerts_rows:
                execute_values(cur, """
                    INSERT INTO alerts (id, query_run_id, finca_id, severity, label, message, source, created_at)
                    VALUES %s
                """, [tuple(r) for r in alerts_rows])
            print(f"  alerts: {len(alerts_rows)} rows migrated")

            # --- source_files ---
            sf_rows = sqlite_conn.execute(
                f"SELECT id, run_id, relative_path, file_type, size_bytes, sha256, content_text, "
                f"created_at FROM source_files WHERE run_id IN ({placeholders})", latest_run_ids
            ).fetchall()
            if sf_rows:
                execute_values(cur, """
                    INSERT INTO source_files (id, query_run_id, relative_path, file_type,
                        size_bytes, sha256, content_text, created_at)
                    VALUES %s
                """, [tuple(r) for r in sf_rows])
            print(f"  source_files: {len(sf_rows)} rows migrated")

        pg.commit()

        print("\nResetting sequences...")
        sequences = [
            "users_id_seq", "persons_id_seq", "person_queries_id_seq",
            "query_runs_id_seq", "fincas_id_seq", "movable_assets_id_seq",
            "query_outputs_id_seq", "alerts_id_seq", "source_files_id_seq",
        ]
        for seq in sequences:
            cur.execute(
                f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {seq.replace('_id_seq', '')}), 1), true)"
            )
        pg.commit()

        print("\nMigration complete!")

    except Exception as exc:
        pg.rollback()
        print(f"\nMigration failed: {exc}")
        raise
    finally:
        cur.close()
        pg.close()
        sqlite_conn.close()


if __name__ == "__main__":
    migrate()
