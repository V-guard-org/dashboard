"""
V-GUARD — Dados de demonstração para o dashboard.

Simula 10 min de viagem perto da UTFPR (GPS, OBD-II e IMU) com 4 eventos
e grava pelo EventManager de verdade (../integracao/events), em demo/.
Serve para ver o mapa e os gráficos enquanto o GPS e o ESP32 não estão
ligados ao vguard.py.

    python3 demo_data.py
    VGUARD_DATA=demo python3 dev_server.py
"""

import math
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "integracao", "events"))
from event_manager import EventManager

OUT = os.path.join(HERE, "demo")
DURATION = 600          # s
IMU_HZ = 10             # a IMU real vai a 100 Hz; 10 basta para a demonstração
CENTER = (-25.4395, -49.2687)   # UTFPR, sede Centro
RADIUS = 0.006          # graus, ~650 m

# (segundos desde o início, tipo, score)
EVENTS = [(95, "fadiga", 0.74), (240, "distracao", 0.81),
          (370, "fadiga", 0.92), (510, "distracao", 0.70)]


def photo(label):
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    img = np.full((480, 640, 3), (106, 196, 233), np.uint8)
    cv2.putText(img, "foto de demonstracao", (110, 220),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (83, 70, 38), 2)
    cv2.putText(img, label, (230, 280),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (83, 70, 38), 2)
    return cv2.imencode(".jpg", img)[1].tobytes()


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    manager = EventManager(OUT)
    start = time.time() - DURATION
    pending = list(EVENTS)

    for i in range(DURATION * IMU_HZ):
        t = i / IMU_HZ
        ts = start + t

        # Velocidade oscila entre ~20 e ~60 km/h; uma volta a cada 5 min.
        speed = 40 + 20 * math.sin(t / 45)
        angle = 2 * math.pi * t / 300
        accel = math.cos(t / 45) * 20 / 45 / 3.6 / 9.81  # dv/dt em g (vira m/s² abaixo)

        # Instantes levemente diferentes, como nos sensores reais: o
        # EventManager só consolida amostras com ts maior que o da última
        # consolidação, então duas fontes com o mesmo ts perderiam uma delas.
        if i % IMU_HZ == 0:
            manager.update("gps", {
                "lat": CENTER[0] + RADIUS * math.sin(angle),
                "lon": CENTER[1] + RADIUS * 1.4 * math.sin(angle) * math.cos(angle),
                "speed": round(speed + 1.5, 1),
            }, ts + 0.002)
            # Mesmos campos que o esp32_decoder.py do firmware_telemetria entrega.
            throttle = round(max(0, 18 + 12 * math.cos(t / 45)), 1)
            manager.update("obd", {
                "speed": round(speed),
                "rpm": round(900 + speed * 45),
                "coolant": round(min(90, 60 + t / 10)),
                "load": round(25 + throttle, 1),
                "map": round(35 + throttle * 1.5),
                "iat": 32,
                "throttle": throttle,
                "voltage": 13.8,
                "age_ms": {"speed": 80, "rpm": 120, "coolant": 900, "load": 600,
                           "map": 700, "iat": 950, "throttle": 500, "voltage": 1000},
            }, ts + 0.004)

        # Em m/s², como o esp32_decoder.py entrega (az ≈ 9,81 = gravidade).
        manager.update("imu", {
            "ax": round(9.81 * (accel + 0.02 * math.sin(t * 7)), 2),
            "ay": round(9.81 * 0.15 * math.sin(angle * 2), 2),
            "az": round(9.81 * (1 + 0.03 * math.sin(t * 11)), 2),
        }, ts)

        if pending and t >= pending[0][0]:
            _, kind, score = pending.pop(0)
            manager.record_event(kind, score, photo(kind), ts)

    manager.close()
    print("demo gravada em", OUT)


if __name__ == "__main__":
    main()
