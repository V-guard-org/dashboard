"""
V-GUARD — Servidor de desenvolvimento do dashboard.

Serve o index.html e as rotas de consulta lendo direto o vguard.db do
cartão, em modo somente leitura. É um substituto temporário do backend:
quando a API FastAPI existir, ela implementa as mesmas rotas e o
index.html não muda.

    GET /api/health
    GET /api/events?limit=200
    GET /api/events/<id>            evento + janela de telemetria (RF17)
    GET /api/events/<id>/photo      JPEG
    GET /api/telemetry

    python3 dev_server.py                         # lê ../integracao/dados
    VGUARD_DATA=demo python3 dev_server.py        # dados do demo_data.py
"""

import contextlib
import http.server
import json
import os
import shutil
import sqlite3
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get(
    "VGUARD_DATA", os.path.join(HERE, "..", "integracao", "dados")
)
PORT = int(os.environ.get("PORT", "8000"))

# Teto de linhas por consulta de telemetria (1 linha/s = ~3 h).
TELEMETRY_LIMIT = 10000


def query(sql, params=()):
    # Somente leitura: o vguard.py pode estar gravando ao mesmo tempo.
    path = os.path.abspath(os.path.join(DATA, "vguard.db"))
    with contextlib.closing(
        sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    ) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute(sql, params)]


def event_json(row):
    return {
        "id": row["id"],
        "type": row["type"],
        "ts": row["ts"],
        "score": row["score"],
        "data": json.loads(row["data"]),
        "has_photo": row["photo"] is not None,
        "meta_synced": row["meta_synced"],
        "photo_synced": row["photo_synced"],
    }


def health():
    # ponytail: calculada a partir do SD; no backend vem do POST /health
    # que o Sync envia (ts, link, pending, storage, temperature...).
    pending = query(
        "SELECT"
        " (SELECT COUNT(*) FROM telemetry WHERE synced = 0) AS telemetry,"
        " (SELECT COUNT(*) FROM events WHERE meta_synced = 0) AS events,"
        " (SELECT COUNT(*) FROM events WHERE photo IS NOT NULL"
        "   AND photo_synced = 0 AND meta_synced != 2) AS photos"
    )[0]
    last = query(
        "SELECT (SELECT MAX(ts) FROM events) AS event,"
        " (SELECT MAX(ts) FROM telemetry) AS telemetry"
    )[0]
    usage = shutil.disk_usage(DATA)
    return {
        "ts": time.time(),
        "pending": pending,
        "storage": {"used": usage.used / usage.total, "free_bytes": usage.free},
        "last_event": last["event"],
        "last_telemetry": last["telemetry"],
    }


class Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        params = urllib.parse.parse_qs(url.query)
        parts = [p for p in url.path.split("/") if p]

        try:
            if parts == []:
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    return self.send(200, f.read(), "text/html; charset=utf-8")

            if parts == ["api", "health"]:
                return self.json(health())

            if parts == ["api", "events"]:
                limit = int(params.get("limit", ["200"])[0])
                return self.json([
                    event_json(r) for r in query(
                        "SELECT * FROM events ORDER BY ts DESC LIMIT ?",
                        (limit,)
                    )
                ])

            if len(parts) in (3, 4) and parts[:2] == ["api", "events"]:
                found = query("SELECT * FROM events WHERE id = ?", (parts[2],))
                if not found:
                    return self.send(404, b"evento inexistente", "text/plain")

                if len(parts) == 3:
                    event = event_json(found[0])
                    event["window"] = [
                        {**r, "data": json.loads(r["data"])}
                        for r in query(
                            "SELECT ts, source, data FROM event_window"
                            " WHERE event_id = ? ORDER BY ts",
                            (parts[2],)
                        )
                    ]
                    return self.json(event)

                # O nome do arquivo vem do banco, nunca da URL.
                if parts[3] == "photo" and found[0]["photo"]:
                    path = os.path.join(DATA, "photos", found[0]["photo"])
                    try:
                        with open(path, "rb") as f:
                            return self.send(200, f.read(), "image/jpeg")
                    except FileNotFoundError:
                        # O banco aponta para a foto, mas o arquivo foi
                        # apagado do cartão (ex.: à mão, por privacidade).
                        return self.send(404, b"foto apagada do cartao", "text/plain")

            if parts == ["api", "telemetry"]:
                rows = query(
                    "SELECT ts, data FROM telemetry ORDER BY ts DESC LIMIT ?",
                    (TELEMETRY_LIMIT,)
                )
                return self.json([
                    {"ts": r["ts"], "data": json.loads(r["data"])}
                    for r in reversed(rows)
                ])

            self.send(404, b"rota inexistente", "text/plain")

        except ValueError:
            self.send(400, b"parametro invalido", "text/plain")
        except (sqlite3.Error, OSError) as error:
            self.send(503, str(error).encode(), "text/plain; charset=utf-8")

    def json(self, body):
        self.send(200, json.dumps(body).encode(), "application/json")

    def send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("dashboard em http://localhost:%d (dados: %s)" % (PORT, os.path.abspath(DATA)))
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
