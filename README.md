# VK ответы — ДЗ 2


## Локально

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

## Docker Compose

```sh
docker compose up --build
```

Сайт доступен по адресу [http://localhost:8000/](http://localhost:8000/).
