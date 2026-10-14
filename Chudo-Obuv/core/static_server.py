import threading

from werkzeug.serving import make_server

HOST = "127.0.0.1"


def start(app):
    # Порт 0: система сама выдаёт свободный порт
    server = make_server(HOST, 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://{HOST}:{server.server_port}/"
