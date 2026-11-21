# VK ответы — ДЗ 4

Скопируйте `.env.example` в `.env.docker`. В этом файле укажите `DB_HOST=db` и задайте `DJANGO_SECRET_KEY` и `POSTGRES_PASSWORD`.

Из корня проекта запустите Docker Compose.

```sh
docker compose --env-file .env.docker up -d --build --wait
```

Сайт откроется на [localhost:8000](http://localhost:8000/).

## Проверка

```sh
docker compose --env-file .env.docker exec web python manage.py test
docker compose --env-file .env.docker exec web python manage.py fill_db 2  # данные для ручной проверки
```
