# VK ответы — ДЗ 2

Для локального запуска нужен Python 3.12. Команды выполняются из корня репозитория.

## Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

## Linux/macOS

```sh
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python manage.py migrate
./.venv/bin/python manage.py runserver
```

## Ключ Django

Для учебного запуска используется запасной ключ из настроек. Чтобы задать свой `DJANGO_SECRET_KEY`, перед запуском сервера выполни в том же терминале одну из команд.

Windows PowerShell

```powershell
$env:DJANGO_SECRET_KEY = "your-secret-key"
```

Linux/macOS

```sh
export DJANGO_SECRET_KEY="your-secret-key"
```

При локальном запуске файл `.env` автоматически не загружается. Docker Compose читает его и передаёт `DJANGO_SECRET_KEY` контейнеру. Для Compose можно скопировать `.env.example` в `.env` и заменить `replace-me` своим ключом.

## Docker Compose

```sh
docker compose up --build
```

Сайт доступен по адресу [http://localhost:8000/](http://localhost:8000/).
