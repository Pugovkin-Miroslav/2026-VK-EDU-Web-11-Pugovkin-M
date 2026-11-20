# VK ответы — ДЗ 3

Команды выполняются из корня репозитория. Проект использует PostgreSQL. Применение миграций создаёт таблицы в PostgreSQL.

## Файлы окружения

Скопируй `.env.example` в `.env.local` для запуска Django на компьютере и в `.env.docker` для запуска через Compose.

Windows PowerShell

```powershell
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
if (-not (Test-Path .env.docker)) { Copy-Item .env.example .env.docker }
```

Linux/macOS

```sh
test -f .env.local || cp .env.example .env.local
test -f .env.docker || cp .env.example .env.docker
```

Заполни `DJANGO_SECRET_KEY` и `POSTGRES_PASSWORD` в каждом файле своими значениями. Для нового ключа или пароля можно сгенерировать случайную строку из шестнадцатеричных символов командой `python -c "from secrets import token_hex; print(token_hex(32))"`. Такой формат одинаково читается в обоих файлах.

- В `.env.docker` задай `DB_HOST=db` и `DB_PORT=5432`. Compose подставляет настройки из файла, указанного через `--env-file`.
- В `.env.local` оставь `DB_HOST=127.0.0.1` и укажи порт своего PostgreSQL. Django загружает этот файл автоматически. Переменные, уже заданные в терминале, имеют приоритет.

## Docker Compose

```sh
docker compose --env-file .env.docker up -d --build --wait
docker compose --env-file .env.docker exec web python manage.py check
docker compose --env-file .env.docker exec web python manage.py migrate --check
```

Сайт доступен по адресу [http://localhost:8000/](http://localhost:8000/). При запуске `web` ждёт готовности PostgreSQL и применяет миграции. Данные PostgreSQL хранятся в именованном volume `postgres_data` и сохраняются после `docker compose --env-file .env.docker down`.

## Локальный запуск

Нужен Python 3.12 и запущенный PostgreSQL. Создай пользователя и БД по значениям из `.env.local`. Для запуска Django локально с PostgreSQL из Compose можно поднять только сервис базы.

```sh
docker compose --env-file .env.docker up -d --wait db
```

В этом случае `POSTGRES_DB`, `POSTGRES_USER` и `POSTGRES_PASSWORD` должны совпадать в обоих файлах. Задай в `.env.local` значение `DB_PORT`, равное `POSTGRES_HOST_PORT` в `.env.docker`. Если порт 5432 уже занят, поменяй `POSTGRES_HOST_PORT`, например на 5433. Внутренний порт в `.env.docker` при этом остаётся 5432.

PostgreSQL использует `POSTGRES_DB`, `POSTGRES_USER` и `POSTGRES_PASSWORD` при первом запуске с пустым volume. У уже созданной БД пароль меняется в самом PostgreSQL.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

### Linux/macOS

```sh
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python manage.py migrate
./.venv/bin/python manage.py runserver
```
