# V-GUARD — Dashboard

Painel web para consultar os eventos de fadiga e distração, as fotos, os
dados do carro, a trajetória no mapa, a telemetria e a saúde do dispositivo
(RF25 a RF27, RF32). É uma página só (`index.html`), sem etapa de compilação.

```
Raspberry Pi ── Sync ──► backend (FastAPI + PostgreSQL) ──/api/*──► index.html (navegador)
```

A página fala só com as rotas `/api/*` descritas em [Rotas](#rotas-contrato-com-o-backend),
servidas pelo [backend](https://github.com/V-guard-org/backend), com login.

## Arquivos

| Arquivo        | O que é                                                         |
|----------------|-----------------------------------------------------------------|
| `index.html`   | A página inteira: HTML, CSS e JavaScript                        |
| `demo_data.py` | Gera 10 min de viagem simulada em `demo/` e envia ao backend    |

## Abrir o dashboard

As pastas ficam lado a lado em `v-guard/`:

```
v-guard/
├── integracao/     # vguard.py grava em integracao/dados/
├── backend/
└── dashboard/
```

```bash
cd ../backend && DASHBOARD_PASSWORD=escolha-uma-senha uvicorn app:app --host 0.0.0.0
```

Abra <http://localhost:8000> e entre com o usuário `vguard` e a senha
escolhida. O backend serve este `index.html`. Para os dados chegarem, o
`vguard.py` precisa estar rodando com `VGUARD_BACKEND`, `VGUARD_DEVICE` e
`VGUARD_TOKEN`: veja o README do backend.

### Com dados de demonstração

Enquanto o GPS e o ESP32 não estão ligados, o mapa, os mostradores do carro
e a telemetria ficam vazios com os dados reais. Para vê-los funcionando, suba
um segundo backend com um banco só para a demonstração:

```bash
createdb vguard_demo
cd ../backend && export DATABASE_URL=dbname=vguard_demo PHOTOS_DIR=fotos_demo
python3 app.py novo-dispositivo demo
DASHBOARD_PASSWORD=demo uvicorn app:app --port 8001
```

O `novo-dispositivo` mostra duas linhas `export VGUARD_DEVICE=...` e
`export VGUARD_TOKEN=...`. Em outro terminal, dentro de `dashboard/`, cole
essas duas linhas e rode:

```bash
VGUARD_BACKEND=http://localhost:8001/api python3 demo_data.py
```

No fim ele diz se a demo foi enviada e, se não foi, o motivo: sem
`VGUARD_BACKEND`, token recusado ou backend fora do ar.

Abra <http://localhost:8001> (usuário `vguard`, senha `demo`). O `demo_data.py`
simula 10 min de viagem perto da UTFPR, com 4 eventos, GPS, IMU e todos os
PIDs do OBD-II, grava em `demo/` com o `EventManager` de verdade e envia uma
vez pelo `Sync` de verdade. Os dados reais não são tocados. Rodar de novo
envia outra viagem, com eventos novos.

A página se atualiza sozinha a cada 10 s. Leaflet (mapa), Chart.js
(gráficos) e a fonte Inter vêm de CDN, então o navegador precisa de internet.

## O que a página mostra

O visual segue o painel do [OBD-II](https://github.com/V-guard-org/OBD-II)
(`painel.h`): tema escuro, cartões arredondados, mostradores de ponteiro e
os mesmos pontos de quebra para celular (3 mostradores lado a lado até 360 px).

| Bloco | O que mostra |
|---|---|
| **Saúde** | Último evento, eventos, fotos e telemetria ainda no cartão da Pi, ocupação do cartão, conexão (Wi-Fi ou 4G, último contato e dados no 4G) e temperatura da Pi |
| **Carro** | Mostradores de rotação, velocidade e arrefecimento, e "Outros dados" com os demais PIDs (ver [campos](#campos-da-telemetria)) |
| **Eventos** | Lista com horário, tipo e score |
| **Detalhe do evento** | Foto, sensores no instante do evento e gráfico da janela de ±10 s |
| **Trajetória** | Caminho do GPS, última posição e os eventos no mapa |
| **Telemetria** | Velocidade do OBD-II e do GPS e rotação ao longo do tempo |

Comportamentos:

- **Dados do carro:** é sempre a **última leitura**, não uma média. Cada valor
  mostra "Atualizado há X s", contando a idade que o ESP32 informou. Leitura
  com mais de 5 min, ou carro sem resposta, fica apagada, como no painel. O
  arrefecimento fica vermelho a partir de 105 °C ("Temperatura alta") e avisa
  "Motor superaquecendo" a partir de 115 °C. São valores iniciais, a ajustar no carro.
- **Evento, gráfico e mapa ligados:** clicar num evento marca o instante dele no
  gráfico de telemetria e leva o mapa até o local; clicar num marcador do mapa
  seleciona o evento na tabela.
- **Foto que não carrega:** aparece "Foto indisponível", em vez de imagem quebrada.
  Foto que ainda espera o envio aparece como "Foto no cartão da Pi, esperando o envio".
- **Conexão:** fica em alerta, como "Sem contato", se a Pi não fala há mais de 10 min
  (o `Sync` espera até 10 min entre tentativas depois de falhas).
- **Temperatura da Pi:** alerta a partir de 70 °C e crítico a partir de 80 °C, quando a
  Pi 4 começa a reduzir o desempenho.
- **Números com vírgula decimal**, como em português.

| Bloco | Com os dados reais, hoje |
|---|---|
| Saúde, eventos, detalhe e foto | ✅ funcionam com o `vguard.py` e a webcam |
| Carro, janela de ±10 s e telemetria | ⏳ vazios até o ESP32 enviar IMU e OBD-II (o demo simula) |
| Trajetória | ⏳ vazia até o receptor GNSS ser ligado à Pi (o leitor já existe no `integracao/`) |

## Rotas (contrato com o backend)

Todas devolvem JSON, exceto a foto. `ts` é sempre em segundos desde 1970 (Unix).
O backend implementa as mesmas rotas, protegidas por login.

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

- `pending` e `storage`: o que ainda está no cartão da Pi e a ocupação dele.
  No backend vêm do último `POST /health` do `Sync` e são `null` até o primeiro;
  a página mostra "—".
- O backend devolve também `link` (`"wifi"`, `"cellular"` ou `null`),
  `last_contact` (quando o servidor recebeu o último `POST /health`),
  `temperature` (°C da Raspberry Pi) e `cellular_bytes` (bytes no 4G desde que a
  Pi ligou), mostrados nos cartões "Conexão" e "Temperatura da Pi".

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
  "photo_pending": false
}]
```

- `type`: `"fadiga"` ou `"distracao"`; tipos novos aparecem com o nome cru.
- `data`: a última amostra de cada sensor no instante do evento. Pode vir `{}`.
- `has_photo`: a foto já chegou ao servidor.
- `photo_pending`: a foto existe, mas ainda está no cartão da Pi esperando o envio.
  Com os dois `false`, o evento não tem foto.

### `GET /api/events/<id>`

O mesmo evento, mais `window`: as amostras de 10 s antes até 10 s depois, na
frequência original dos sensores.

```json
{"...": "...", "window": [{"ts": 1792787796.2, "source": "obd", "data": {"speed": 21, "rpm": 1851}}]}
```

### `GET /api/events/<id>/photo`

O JPEG da foto (`image/jpeg`), ou 404 se o evento não tiver foto.

### `GET /api/telemetry`

Telemetria consolidada, 1 linha por segundo (a última amostra de cada
segundo), em ordem de tempo: as 10 000 linhas mais recentes, cerca de 3 h.

```json
[{"ts": 1792787296.2, "data": {
  "gps": {"lat": -25.43, "lon": -49.26, "speed": 41.5},
  "obd": {"speed": 40, "rpm": 2700, "coolant": 88, "load": 52.0,
          "age_ms": {"speed": 80, "rpm": 120, "coolant": 900, "load": 600}},
  "imu": {"ax": 0.12, "ay": 0.0, "az": 9.81}}}]
```

### Campos da telemetria

**OBD-II**, como o `esp32_decoder.py` do
[firmware_telemetria](https://github.com/V-guard-org/firmware_telemetria) entrega:

| Campo      | PID  | Nome na página               | Unidade |
|------------|------|------------------------------|---------|
| `rpm`      | 0C   | Rotação (mostrador)          | rpm     |
| `speed`    | 0D   | Velocidade (mostrador)       | km/h    |
| `coolant`  | 05   | Arrefecimento (mostrador)    | °C      |
| `load`     | 04   | Carga do motor               | %       |
| `map`      | 0B   | Pressão absoluta da admissão | kPa     |
| `iat`      | 0F   | Temperatura da admissão      | °C      |
| `throttle` | 11   | Posição da borboleta         | %       |
| `voltage`  | 42   | Tensão informada pela ECU    | V       |
| `age_ms`   | —    | Idade de cada valor, em ms   | —       |

Um campo novo do OBD-II aparece sozinho em "Outros dados", com o nome cru;
para ter nome e unidade, basta uma linha na constante `OBD` do `index.html`.

**IMU:** `ax`, `ay`, `az` em m/s² e `gx`, `gy`, `gz` em °/s. A página usa `ax`
na janela do evento.

**GPS:** `lat`, `lon` e `speed` (km/h), gravados pelo `GpsReader` do `integracao/`.

## Testes

As rotas têm os testes do backend (`test_app.py` e `test_e2e.py`, no
repositório dele).

## Pendências

- **GPS (RF02):** o leitor existe na Pi; o mapa fica vazio até o receptor GNSS
  ser ligado.
- **Período da telemetria:** hoje vêm sempre as últimas ~3 h. Com viagens
  longas, vale escolher o dia ou o intervalo.
- **Mais de um veículo:** as rotas ganham o dispositivo, por exemplo
  `/api/devices/<id>/events`.
