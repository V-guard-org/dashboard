# V-GUARD — Dashboard

Painel web para consultar os eventos, as fotos, a saúde do dispositivo,
a trajetória no mapa e a telemetria (RF25 a RF27, RF32).

Por enquanto não existe backend: o `dev_server.py` faz o papel dele,
lendo direto o banco que o `vguard.py` grava no cartão
([V-guard-org/integracao](https://github.com/V-guard-org/integracao)).
Quando a API FastAPI existir, ela implementa as **mesmas rotas** abaixo e
o `index.html` não muda.

```
integracao/dados/vguard.db ──(somente leitura)──► dev_server.py ──/api/*──► index.html
                                                   (no futuro: API FastAPI + PostgreSQL)
```

## Executar

As pastas `dashboard/` e `integracao/` precisam estar lado a lado:

```
v-guard/
├── integracao/     # vguard.py grava em integracao/dados/
└── dashboard/
```

Com os dados reais do `vguard.py`:

```bash
python3 dev_server.py
```

Abra <http://localhost:8000>. A página se atualiza sozinha a cada 10 s,
então dá para deixar aberta enquanto o `vguard.py` roda.

Só a biblioteca padrão do Python é necessária. Leaflet (mapa) e Chart.js
(gráficos) vêm de CDN, então o navegador precisa de internet.

### Dados de demonstração

Enquanto o GPS e o ESP32 não estão ligados, o mapa e a telemetria ficam
vazios. Para vê-los funcionando:

```bash
python3 demo_data.py
```

```bash
VGUARD_DATA=demo PORT=8001 python3 dev_server.py
```

O `demo_data.py` simula 10 min de viagem perto da UTFPR, com 4 eventos, e
grava em `demo/` usando o `EventManager` de verdade. Os dados reais não
são tocados.

| Variável        | Padrão                 | Uso                                    |
|-----------------|------------------------|----------------------------------------|
| `VGUARD_DATA`   | `../integracao/dados`  | Pasta com `vguard.db` e `photos/`      |
| `PORT`          | `8000`                 | Porta do servidor (só em `127.0.0.1`)  |

## O que a página mostra

| Bloco               | Fonte                    | Hoje                                         |
|---------------------|--------------------------|----------------------------------------------|
| Saúde (cartões)     | `GET /api/health`        | ✅ pendências e ocupação do cartão            |
| Lista de eventos    | `GET /api/events`        | ✅ eventos reais da câmera                    |
| Detalhe e foto      | `GET /api/events/<id>`   | ✅ foto real; sensores vazios sem o ESP32     |
| Janela de ±10 s     | `window` do evento       | ⏳ vazia até o ESP32 enviar IMU e OBD-II      |
| Trajetória no mapa  | `GET /api/telemetry`     | ⏳ vazia até existir o leitor do GPS (RF02)   |
| Gráfico de telemetria | `GET /api/telemetry`   | ⏳ vazio até o ESP32 estar conectado          |

## Rotas (contrato com o backend)

Todas devolvem JSON, exceto a foto. `ts` é sempre em segundos desde 1970 (Unix).

### `GET /api/health`

```json
{
  "ts": 1792787908.9,
  "pending": {"telemetry": 0, "events": 3, "photos": 3},
  "storage": {"used": 0.78, "free_bytes": 8046424064},
  "last_event": 1792784688.7,
  "last_telemetry": null
}
```

No backend, isto vem do último `POST /health` que o `Sync` envia
(ele também traz `link`, `temperature`, `cellular_bytes` e `last_contact`).

### `GET /api/events?limit=200`

Do mais novo para o mais antigo:

```json
[{
  "id": "676eed87-9c31-4cda-af1e-2d06a736a5d9",
  "type": "fadiga",
  "ts": 1792784688.7,
  "score": 0.7,
  "data": {"gps": {...}, "imu": {...}, "obd": {...}},
  "has_photo": true,
  "meta_synced": 0,
  "photo_synced": 0
}]
```

- `type`: `"fadiga"` ou `"distracao"`.
- `data`: a última amostra de cada sensor no instante do evento. Pode vir `{}`.
- `meta_synced` / `photo_synced`: `0` pendente, `1` enviado, `2` recusado.
  Só fazem sentido lendo o cartão; no backend tudo já chegou.

### `GET /api/events/<id>`

O mesmo evento, mais `window`: as amostras de 10 s antes até 10 s depois.

```json
{"...": "...", "window": [{"ts": 1792787796.2, "source": "obd", "data": {"speed": 21, "rpm": 1851}}]}
```

### `GET /api/events/<id>/photo`

O JPEG da foto (`image/jpeg`), ou 404 se o evento não tiver foto.

### `GET /api/telemetry`

Telemetria consolidada, 1 linha por segundo, em ordem de tempo: as
10 000 linhas mais recentes.

```json
[{"ts": 1792787296.2, "data": {"gps": {"lat": -25.43, "lon": -49.26, "speed": 41.5},
                               "obd": {"speed": 40, "rpm": 2700, "coolant": 88},
                               "imu": {"ax": 0.01, "ay": 0.0, "az": 1.0}}}]
```

Campos que a página usa: `gps.lat`, `gps.lon`, `gps.speed` (km/h),
`obd.speed` (km/h), `obd.rpm` e `imu.ax` (g). **O formato do GPS ainda não
existe no `integracao/`**: o leitor do GPS precisa gravar com esses nomes.

## Pendências

- **Backend:** trocar o `dev_server.py` pela API FastAPI + PostgreSQL com as mesmas rotas.
  Quando houver mais de um veículo, as rotas ganham o dispositivo (ex.: `/api/devices/<id>/events`).
- **Autenticação:** o `dev_server.py` só escuta em `127.0.0.1` e não tem login; o backend precisa ter.
- **GPS (RF02):** sem o leitor, o mapa fica vazio com os dados reais.
