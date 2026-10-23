"""
Testa as rotas do dev_server.py com os dados do demo_data.py, gravados
numa pasta temporária. Sobe o servidor numa porta livre, então pode rodar
com outro dev_server.py aberto.

    python3 test_dev_server.py
"""

import json
import tempfile
import threading
import urllib.error
import urllib.request

import demo_data
import dev_server


def get(base, path):
    """(status, content-type, corpo) de um GET."""
    try:
        with urllib.request.urlopen(base + path) as r:
            return r.status, r.headers["Content-Type"], r.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers["Content-Type"], error.read()


def get_json(base, path):
    status, kind, body = get(base, path)
    assert status == 200 and kind == "application/json", (path, status, body)
    return json.loads(body)


def serve(data_dir):
    dev_server.DATA = data_dir
    dev_server.Handler.log_message = lambda *args: None   # sem log por requisição
    server = dev_server.http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), dev_server.Handler
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, "http://127.0.0.1:%d" % server.server_port


def test_routes():
    demo_data.OUT = tempfile.mkdtemp()
    demo_data.main()
    server, base = serve(demo_data.OUT)

    try:
        status, kind, body = get(base, "/")
        assert status == 200 and kind.startswith("text/html")
        assert b"V-GUARD" in body

        health = get_json(base, "/api/health")
        assert health["pending"]["telemetry"] == 600
        assert health["pending"]["events"] == len(demo_data.EVENTS)
        assert 0 < health["storage"]["used"] < 1
        assert health["last_event"] < health["last_telemetry"]

        # Do mais novo para o mais antigo, com os tipos do demo_data.
        events = get_json(base, "/api/events")
        assert [e["type"] for e in events] == [t for _, t, _ in reversed(demo_data.EVENTS)]
        assert [e["ts"] for e in events] == sorted((e["ts"] for e in events), reverse=True)
        assert get_json(base, "/api/events?limit=2") == events[:2]

        # Cada evento tem os três sensores e a janela de ±10 s.
        for summary in events:
            event = get_json(base, "/api/events/" + summary["id"])
            assert set(event["data"]) == {"gps", "imu", "obd"}
            assert {w["source"] for w in event["window"]} == {"gps", "imu", "obd"}
            assert all(abs(w["ts"] - event["ts"]) <= 10.01 for w in event["window"])

            status, kind, body = get(base, "/api/events/%s/photo" % summary["id"])
            if summary["has_photo"]:      # o demo só gera foto se houver OpenCV
                assert status == 200 and kind == "image/jpeg"
                assert body[:2] == b"\xff\xd8"
            else:
                assert status == 404

        # Telemetria em ordem de tempo, 1 linha/s, com GPS para o mapa.
        telemetry = get_json(base, "/api/telemetry")
        assert len(telemetry) == 600
        assert [r["ts"] for r in telemetry] == sorted(r["ts"] for r in telemetry)
        assert all({"lat", "lon"} <= set(r["data"]["gps"]) for r in telemetry)

        # Erros: id inexistente, tentativa de ler outro arquivo, parâmetro ruim.
        assert get(base, "/api/events/nao-existe")[0] == 404
        assert get(base, "/api/events/nao-existe/photo")[0] == 404
        assert get(base, "/api/events/..%2F..%2Fvguard.db/photo")[0] == 404
        assert get(base, "/api/events?limit=abc")[0] == 400
        assert get(base, "/api/nada")[0] == 404
    finally:
        server.shutdown()


def test_without_database():
    # Pasta sem vguard.db (o vguard.py ainda não rodou): 503, sem derrubar o servidor.
    server, base = serve(tempfile.mkdtemp())
    try:
        assert get(base, "/api/events")[0] == 503
        assert get(base, "/api/health")[0] == 503
        assert get(base, "/")[0] == 200
    finally:
        server.shutdown()


if __name__ == "__main__":
    test_routes()
    test_without_database()
    print("OK")
