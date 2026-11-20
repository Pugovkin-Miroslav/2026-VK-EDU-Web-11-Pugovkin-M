# VK ответы — ДЗ 3

Команды выполняются из корня репозитория. Проект использует PostgreSQL. Применение миграций создаёт таблицы в PostgreSQL.

## Файлы окружения

Скопируйте `.env.example` в `.env.local` для запуска Django на компьютере и в `.env.docker` для запуска через Compose.

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

Укажите собственные значения `DJANGO_SECRET_KEY` и `POSTGRES_PASSWORD` в каждом файле. Для нового ключа или пароля можно сгенерировать случайную строку из шестнадцатеричных символов командой `python -c "from secrets import token_hex; print(token_hex(32))"`. Такой формат одинаково читается в обоих файлах.

- В `.env.docker` задайте `DB_HOST=db` и `DB_PORT=5432`. Compose подставляет настройки из файла, указанного через `--env-file`.
- В `.env.local` оставьте `DB_HOST=127.0.0.1` и укажите порт PostgreSQL. Django загружает этот файл автоматически. Переменные, уже заданные в терминале, имеют приоритет.

## Docker Compose

```sh
docker compose --env-file .env.docker up -d --build --wait
docker compose --env-file .env.docker exec web python manage.py check
docker compose --env-file .env.docker exec web python manage.py migrate --check
```

Сайт доступен на локальном компьютере по адресу [http://localhost:8000/](http://localhost:8000/). При запуске `web` ждёт готовности PostgreSQL и применяет миграции. Данные PostgreSQL хранятся в именованном volume `postgres_data` и сохраняются после `docker compose --env-file .env.docker down`.

## Локальный запуск

Для локального запуска требуются Python 3.12 и запущенный PostgreSQL. Создайте пользователя и БД по значениям из `.env.local`. Если Django подключается к PostgreSQL из Compose, достаточно запустить сервис базы.

```sh
docker compose --env-file .env.docker up -d --wait db
```

В этом случае `POSTGRES_DB`, `POSTGRES_USER` и `POSTGRES_PASSWORD` должны совпадать в обоих файлах. Задайте в `.env.local` значение `DB_PORT`, равное `POSTGRES_HOST_PORT` в `.env.docker`. Если порт 5432 уже занят, измените `POSTGRES_HOST_PORT`, например на 5433. Внутренний порт в `.env.docker` при этом остаётся 5432.

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

## Админка

Для входа в [админку](http://localhost:8000/admin/) создайте суперпользователя.

```sh
docker compose --env-file .env.docker exec web python manage.py createsuperuser
```

При локальном запуске выполните `python manage.py createsuperuser` в активированном виртуальном окружении.

## Наполнение базы тестовыми данными

Для небольшой выборки выполните команду с `ratio=2` после применения миграций.

```sh
docker compose --env-file .env.docker exec web python manage.py fill_db 2
```

При локальном запуске выполните `python manage.py fill_db 2` в активированном виртуальном окружении.

Допустимые значения `ratio` начинаются с 2. Если аргумент опущен, используется 10. Каждый запуск добавляет новые записи.

| Сущность | Количество за один запуск |
| --- | ---: |
| Пользователи, профили и теги | По `ratio` |
| Вопросы | `ratio × 10` |
| Ответы | `ratio × 100` |
| Лайки вопросов и ответов суммарно | `ratio × 200` |

Для проверки объёма из рубрики укажите `10000`. Для превышения строгих порогов из описания задания укажите `10001`.

## Проверка запросов

Установите `DJANGO_DEBUG=true` в `.env.docker` для запуска через Compose или в `.env.local` для локального запуска. При локальном запуске остановите и снова запустите `runserver`. В Compose примените изменённые переменные командой

```sh
docker compose --env-file .env.docker up -d --wait web
```

1. Откройте [главную страницу](http://localhost:8000/) и выберите панель **SQL** в Django Debug Toolbar.
2. Сравните число запросов на страницах с разным числом вопросов или ответов. Проверьте главную, список популярных вопросов, страницу тега, карточку вопроса и списки в админке.
3. Для проверки режима без панели задайте `DJANGO_DEBUG=false` и примените настройки тем же способом. В этом режиме для отсутствующего вопроса или тега отображается страница 404 сайта.

Для проверки автоматических тестов в Docker выполните следующую команду. Панель отладки во время тестов отключена.

```sh
docker compose --env-file .env.docker exec web python manage.py test
```
