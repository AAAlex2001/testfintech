# Gate NambaOne

Платёжный гейт для [Namba One](https://merchant-api-docs.rps.kg/): оплата по одноразовой платёжной ссылке, статус платежа, вебхук об оплате, возврат и статус возврата.

## Как это работает

Платформа (sbank) хочет принять оплату и вызывает гейт. Гейт создаёт в Namba One одноразовую платёжную ссылку и возвращает её платформе. Клиент оплачивает по ссылке в приложении Namba One. Namba One присылает гейту вебхук, а гейт перепроверяет статус у провайдера и сообщает платформе, что инвойс оплачен или не оплачен.

Путь одного запроса по коду, например `POST /v2/sale`:

1. `api/v2/v2.py` регистрирует роуты.
2. `gate_lib/api/v2.py` принимает запрос и проверяет его поля: пустой `invoice_id`, отрицательная сумма и т. п. дают 422.
3. `gate_nambaone/gate_nambaone.py`, метод `sale_without_card`, выполняет сценарий:
   - проверяет `terminal_data`;
   - через `mappers.py` переводит сомы в тыйыны и собирает запрос;
   - через `client.py` отправляет подписанный запрос в Namba One;
   - собирает ответ платформе.
4. Если что-то пошло не так, `client.py` бросает понятную ошибку (таймаут, провайдер недоступен, мусор в ответе, отказ провайдера), а метод гейта превращает её в статус `failed` или `pending`. Таблица ниже.

## Запуск через Docker

```bash
docker compose up --build
```

Сервис поднимется на http://localhost:8000. Ничего настраивать не нужно: у всех переменных есть значения по умолчанию, список лежит в [.env.example](.env.example).

## Запуск без Docker

Нужен Python 3.12 или новее. Команды ниже для Windows PowerShell, запускать из папки `gate-nambaone`:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install poetry
poetry install
python src/main.py
```

На Linux и macOS вместо второй строки: `source .venv/bin/activate`.

## Автотесты

```bash
poetry run pytest
```

Тесты не ходят в сеть: ответы Namba One и sbank подменяются через `pytest-httpx`. На каждый метод есть сценарии: успешный запрос, отказ провайдера, невалидный запрос, невалидный ответ, пустой ответ, таймаут, 5xx.

| Файл | Что проверяет |
|---|---|
| `tests/test_sale.py` | создание платежа |
| `tests/test_status.py` | статус платежа |
| `tests/test_invoice_notification.py` | вебхук об оплате |
| `tests/test_refund.py` | возврат |
| `tests/test_refund_status.py` | статус возврата |
| `tests/test_signature.py` | подпись запросов |
| `tests/test_service.py` | ping, схема настроек, trace id |
| `tests/data.py` | общие тестовые данные |

## Как проверить руками

Проще всего через Swagger: откройте http://localhost:8000/api/openapi, выберите метод, нажмите **Try it out**, вставьте JSON и нажмите **Execute**.

**1. Сервис жив.** `GET /v2/ping` отвечает `pong`.

**2. Создание платежа.** `POST /v2/sale`:

```json
{
  "invoice_id": "test-invoice-1",
  "amount": "100.50",
  "currency_code": "KGS",
  "finish_url": "https://shop.example.com/finish",
  "terminal_data": {
    "provider_base_url": "https://namba-one.example.com",
    "merchant_account_guid": "159e7e3b-94e1-48c7-bec5-952949f7935f",
    "secret_key": "test-secret"
  }
}
```

Без настоящего Namba One ответ будет таким: провайдер недоступен, платёж не создан, сервис не упал.

```json
{"status": "failed", "code": "validation_error", "message": "Provider is unavailable: ...", ...}
```

С реальными доступами от Namba One (`provider_base_url`, `merchant_account_guid`, `secret_key`) вернётся `"status": "pending"` и `redirect.url` — ссылка на оплату.

**3. Проверка валидации.** Если отправить в `/v2/sale` тело `{"invoice_id": ""}`, придёт 422 со списком проблемных полей. Если в `terminal_data` передать `"merchant_account_guid": "abc"`, придёт `failed` с сообщением `Terminal data is not valid: merchant_account_guid`.

**4. Остальные методы** проверяются так же:

- `/v2/status` с полями `invoice_id`, `currency_code`, `terminal_data`;
- `/v2/refund` с полями `refund_id`, `external_id`, `amount`, `currency_code`, `terminal_data`;
- `/v2/refund_status` с полями `refund_id`, `currency_code`, `terminal_data`.

При недоступном провайдере запросы статуса вернут `pending`: итог неизвестен, спросим позже.

**5. Вебхук.** `POST /nambaone/callback/invoice`:

```json
{"type": "PAYMENT_ORDER", "data": {"guid": "g-1", "externalId": "test-invoice-1", "status": "COMPLETED"}}
```

Локально sbank нет, поэтому ответ будет `503 RETRY`: гейт не смог подтвердить оплату и просит Namba One повторить вебхук. Полный успешный путь покрыт автотестом `test_invoice_notification_success`.

Логи сервис пишет в консоль в формате JSON. У всех строк одного запроса общий `trace_id`.

## Методы

| Метод гейта | Роут | Запрос в Namba One |
|---|---|---|
| `sale_without_card` | `POST /v2/sale` | `POST /public/merchant/payment/v2/{merchant}/one-time` |
| `status` | `POST /v2/status` | `GET /public/merchant/payment/v1/{merchant}/one-time/{invoice_id}` |
| `notification_invoice` | `POST /nambaone/callback/invoice` | `GET .../one-time/{invoice_id}`: статус перезапрашивается |
| `refund` | `POST /v2/refund` | `POST /public/merchant/payment/v1/{merchant}/refund/{refund_id}` |
| `refund_status` | `POST /v2/refund_status` | `GET /public/merchant/payment/v1/{merchant}/refund/{refund_id}` |

Суммы: платформа передаёт сомы (`100.50`), Namba One работает в тыйынах (`"10050"`). Поддерживается только `KGS`.

## terminal_data

```json
{
  "gate_connection": {
    "url": "http://gate-nambaone:8000/v2"
  },
  "provider_base_url": "https://api.namba-one.kg",
  "merchant_account_guid": "159e7e3b-94e1-48c7-bec5-952949f7935f",
  "secret_key": "secret from Namba One",
  "callback_url": "https://gate.example.com/nambaone/callback/invoice",
  "refund_callback_url": null,
  "proxy_url": null
}
```

| Поле | Обязательное | Параметр Namba One |
|---|---|---|
| `gate_connection.url` | да | не передаётся провайдеру: адрес гейта, по нему платформа шлёт запросы |
| `provider_base_url` | да | `{baseUrl}` |
| `merchant_account_guid` | да | `{merchantAccountGuid}` в URI |
| `secret_key` | да | ключ HMAC-SHA512 для подписи |
| `callback_url` | нет | `webhookUrl` платёжной ссылки |
| `refund_callback_url` | нет | `webhookUrl` возврата |
| `proxy_url` | нет | прокси для запросов к провайдеру |

## Статусы

| Namba One (платёж) | Платформа |
|---|---|
| `COMPLETED`, `REFUNDED` | `complete` |
| `CANCELED`, `FAILED`, `EXPIRED` | `failed` |
| остальные и неизвестные | `pending` |

| Namba One (возврат) | Платформа |
|---|---|
| `COMPLETED` | `complete` |
| `CANCELED`, `FAILED`, `EXPIRED` | `failed` |
| `CREATED`, `PROCESSING`, `STUCK` и неизвестные | `pending` |

Неизвестный статус всегда считается `pending`: финализировать деньги наугад нельзя.

## Обработка ошибок

| Ситуация | sale | status / refund_status | refund | вебхук |
|---|---|---|---|---|
| Невалидное тело запроса | 422 | 422 | 422 | 422 |
| Невалидный terminal_data, валюта, сумма | `failed` | `pending` | `failed` | 503 |
| Провайдер ответил `status: ERROR` | `failed` | `pending` | `failed` | 503 |
| Невалидный или пустой ответ | `failed` | `pending` | `pending` | 503 |
| Таймаут, сетевая ошибка, 5xx | `failed` | `pending` | `pending` | 503 |

- **sale**: деньги ещё не списаны, поэтому любая ошибка даёт `failed`.
- **status**: итог неизвестен, платформа спросит ещё раз.
- **refund**: после таймаута или непонятного ответа возврат мог создаться у провайдера. Поэтому гейт возвращает `pending`, итог покажет `refund_status`. `refund_id` передаётся в URI и служит ключом идемпотентности.
- **вебхук**: статусу из тела не доверяем и перезапрашиваем его у провайдера, так поддельный вебхук не проведёт платёж. Если подтвердить итог не удалось, отвечаем 503: Namba One повторяет вебхук каждые 5 секунд в течение часа. Если инвойс уже финальный, отвечаем 200 и провайдера не спрашиваем.

Коды ошибок в поле `code`:

- **sale** при любой ошибке возвращает `validation_error`. Причина передаётся в `message`, исходный код ошибки пишется в лог (`sale_failed`).
- **Остальные методы** возвращают `validation_error`, `provider_timeout`, `provider_unavailable`, `invalid_provider_response` или `errorCode` самого Namba One.

## Структура

```
src/
├── main.py                  # FastAPI-приложение, middleware, lifespan
├── settings.py
├── api/                     # HTTP-слой: только роуты и зависимости
│   ├── deps.py
│   ├── notifications.py     # вебхук Namba One
│   └── v2/v2.py             # роуты протокола v2
├── gate_nambaone/           # интеграция с Namba One
│   ├── gate_nambaone.py     # GateNambaOne: сценарии и выбор статуса при ошибке
│   ├── client.py            # NambaOneClient: HTTP, подпись, разбор ответа
│   ├── mappers.py           # протокол платформы <-> модели Namba One
│   ├── signature.py         # HMAC-SHA512 подпись
│   ├── const.py             # статусы и их маппинг
│   ├── exceptions.py        # ошибки гейта
│   └── schemas/             # terminal_data, модели API, вебхук
├── gate_lib/                # локальная замена GitLab-зависимости: протокол v2 и фабрики роутов
├── sbank_client/            # локальная замена GitLab-зависимости: клиент платформы
├── utils/                   # локальная замена GitLab-зависимости: логи, httpx-клиент, middleware
└── tests/
```

Зависимости направлены в одну сторону: `api` → `gate_nambaone` → `gate_lib` / `sbank_client` / `utils`. Роуты `gate_lib` знают только протокол `PaymentGate`, а не конкретный гейт.

## Допущения

- `gate_lib`, `sbank_client` и `utils` реализованы локально по тем импортам, которые использовал шаблон. Эндпоинты sbank (`/invoices/{id}`, `/invoices/{id}/income`, `/invoices/{id}/fail`, `/terminals/{id}`) придуманы, потому что реальный контракт недоступен.
- Методы шаблона, которых нет у Namba One (оплата картой, p2p, выплаты, баланс), удалены вместе с `cds_client`. Вебхук возврата не входит в задание: статус возврата получается через `refund_status`.
- `parentType` возврата всегда `PAYMENT_QR`, потому что платёж проходит по платёжной ссылке.
- Пример подписи в документации Namba One — заглушка: одна и та же подпись стоит в примерах с разной солью. Алгоритм реализован по описанию, тест сверяет подпись с вектором, посчитанным по этому описанию.
