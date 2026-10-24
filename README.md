# V-GUARD — Dashboard

Painel web para consultar os eventos de fadiga e distração, as fotos, os
dados do carro, a trajetória no mapa, a telemetria e a saúde do dispositivo
(RF25 a RF27, RF32). É uma página só (`index.html`), sem etapa de compilação.

```
                          ┌─► backend (FastAPI + PostgreSQL) ──┐
Raspberry Pi ── Sync ─────┘   V-guard-org/backend              │
                                                               ├──/api/*──► index.html (navegador)
cartão da Pi (vguard.db) ──(somente leitura)──► dev_server.py ─┘
```

A página fala só com as rotas `/api/*` descritas em [Rotas](#rotas-contrato-com-o-backend).
Quem responde pode ser:

- **o [backend](https://github.com/V-guard-org/backend):** o uso de verdade, com
  login e com os dados que a Pi enviou pela internet;
- **o `dev_server.py`, deste repositório:** para desenvolver e testar. Ele lê
  direto o banco que o `vguard.py` grava no cartão
  ([V-guard-org/integracao](https://github.com/V-guard-org/integracao)), sem login.

## Arquivos

| Arquivo              | O que é                                                          |
|----------------------|------------------------------------------------------------------|
| `index.html`         | A página inteira: HTML, CSS e JavaScript                         |
| `dev_server.py`      | Servidor de desenvolvimento, só com a biblioteca padrão do Python |
| `demo_data.py`       | Gera 10 min de viagem simulada em `demo/`                        |
| `test_dev_server.py` | Testes das rotas do `dev_server.py`                              |

## Abrir o dashboard

As pastas ficam lado a lado em `v-guard/`:

```
v-guard/
├── integracao/     # vguard.py grava em integracao/dados/
├── backend/
└── dashboard/
```

### Pelo backend (com login)

```bash
cd ../backend && DASHBOARD_PASSWORD=escolha-uma-senha uvicorn app:app --host 0.0.0.0
```

Abra <http://localhost:8000> e entre com o usuário `vguard` e a senha
escolhida. O backend serve este `index.html`. Para os dados chegarem, o
`vguard.py` precisa estar rodando e enviando: veja o README do backend.

### Pelo `dev_server.py` (sem login, lendo o cartão)

```bash
python3 dev_server.py
```

Abra <http://localhost:8000>. Ele lê `../integracao/dados`, então mostra o
que o `vguard.py` gravou, mesmo sem internet e sem backend.

### Com dados de demonstração

Enquanto o GPS e o ESP32 não estão ligados, o mapa, os mostradores do carro
e a telemetria ficam vazios com os dados reais. Para vê-los funcionando:

```bash
python3 demo_data.py && VGUARD_DATA=demo python3 dev_server.py
```

O `demo_data.py` simula 10 min de viagem perto da UTFPR, com 4 eventos,
GPS, IMU e todos os PIDs do OBD-II, e grava em `demo/` usando o
`EventManager` de verdade. Os dados reais não são tocados.

| Variável        | Padrão                 | Uso                                    |
|-----------------|------------------------|----------------------------------------|
| `VGUARD_DATA`   | `../integracao/dados`  | Pasta com `vguard.db` e `photos/`      |
| `PORT`          | `8000`                 | Porta do servidor (só em `127.0.0.1`)  |
| `VGUARD_EVENTS` | `../integracao/events` | Onde o `demo_data.py` acha o `EventManager` |

O backend e o `dev_server.py` usam a porta 8000. Se aparecer
`Address already in use`, feche o outro (Ctrl+C no terminal dele) ou use
outra porta, por exemplo `PORT=8001 python3 dev_server.py`.

A página se atualiza sozinha a cada 10 s. Leaflet (mapa), Chart.js
(gráficos) e a fonte Inter vêm de CDN, então o navegador precisa de internet.

## O que a página mostra

O visual segue o painel do [OBD-II](https://github.com/V-guard-org/OBD-II)
(`painel.h`): tema escuro, cartões arredondados, mostradores de ponteiro e
os mesmos pontos de quebra para celular (3 mostradores lado a lado até 360 px).

| Bloco | O que mostra |
|---|---|
| **Saúde** | Último evento, eventos, fotos e telemetria ainda no cartão da Pi, e ocupação do cartão |
| **Carro** | Mostradores de rotação, velocidade e arrefecimento, e "Outros dados" com os demais PIDs (ver [campos](#campos-da-telemetria)) |
| **Eventos** | Lista com horário, tipo, score e estado do envio (dados e foto) |
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
- **Foto apagada do cartão:** aparece "Foto indisponível", em vez de imagem quebrada.
- **Números com vírgula decimal**, como em português.

| Bloco | Com os dados reais, hoje |
|---|---|
| Saúde, eventos, detalhe e foto | ✅ funcionam com o `vguard.py` e a webcam |
| Carro, janela de ±10 s e telemetria | ⏳ vazios até o ESP32 enviar IMU e OBD-II (o demo simula) |
| Trajetória | ⏳ vazia até existir o leitor do GPS (RF02) |

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
  Pi ligou). O `dev_server.py` não tem esses campos, e **a página ainda não os
  mostra** (ver [Pendências](#pendências)).

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

- `type`: `"fadiga"` ou `"distracao"`; tipos novos aparecem com o nome cru.
- `data`: a última amostra de cada sensor no instante do evento. Pode vir `{}`.
- `meta_synced` / `photo_synced`: `0` pendente, `1` enviado, `2` recusado.
  No `dev_server.py` é o estado no cartão. No backend os dados sempre chegaram
  (`1`), e a foto fica `0` enquanto espera o Wi-Fi.

### `GET /api/events/<id>`

O mesmo evento, mais `window`: as amostras de 10 s antes até 10 s depois, na
frequência original dos sensores.

```json
{"...": "...", "window": [{"ts": 1792787796.2, "source": "obd", "data": {"speed": 21, "rpm": 1851}}]}
```

### `GET /api/events/<id>/photo`

O JPEG da foto (`image/jpeg`), ou 404 se o evento não tiver foto ou se ela
foi apagada do cartão.

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

**GPS:** `lat`, `lon` e `speed` (km/h). **Esse formato ainda não existe no
`integracao/`**: o leitor do GPS precisa gravar com esses nomes.

## Testes

```bash
python3 test_dev_server.py
```

Gera os dados de demonstração numa pasta temporária, sobe o servidor numa
porta livre e confere todas as rotas, inclusive os erros: evento inexistente,
tentativa de ler outro arquivo pela URL, parâmetro inválido, foto apagada do
cartão e banco ausente. Imprime `OK` no fim. Precisa do `integracao/` ao lado.

As rotas do backend têm os próprios testes, no repositório dele.

## Pendências

- **Saúde completa (RF32):** mostrar enlace ativo, última comunicação,
  temperatura da Raspberry Pi e dados no 4G. O backend já recebe e devolve
  esses campos; falta exibir.
- **GPS (RF02):** sem o leitor na Pi, o mapa fica vazio com os dados reais.
- **Foto ainda no cartão:** o backend não sabe se um evento tem foto esperando
  o Wi-Fi, então ela aparece como "sem foto" até chegar. Resolve com o
  `EventManager` enviando `has_photo` junto com o evento.
- **Período da telemetria:** hoje vêm sempre as últimas ~3 h. Com viagens
  longas, vale escolher o dia ou o intervalo.
- **Mais de um veículo:** as rotas ganham o dispositivo, por exemplo
  `/api/devices/<id>/events`.
