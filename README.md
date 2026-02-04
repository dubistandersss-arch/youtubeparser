# YouTube парсер (2 этапа)

Этот проект делает две вещи:
1) Находит видео по ключевым словам (в названии или описании).
2) Выгружает топ‑комментарии по указанным ссылкам/ID видео.

## 1. Подготовка ключа API
Нужен ключ YouTube Data API.

Коротко:
1) Зайди на https://console.cloud.google.com/
2) Создай проект.
3) Включи **YouTube Data API v3**.
4) Создай **API key**.

После этого добавь ключ в переменную окружения (самый простой способ):

```bash
export YOUTUBE_API_KEY="ВАШ_КЛЮЧ"
```

Если хочешь, можно добавить строку в конец файла `~/.zshrc`,
чтобы ключ сохранялся навсегда:

```bash
echo 'export YOUTUBE_API_KEY="ВАШ_КЛЮЧ"' >> ~/.zshrc
source ~/.zshrc
```

Или можно временно задать ключ прямо при запуске команды:

```bash
YOUTUBE_API_KEY="ВАШ_КЛЮЧ" python youtube_parser.py search --keywords "тест"
```

## 2. Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Этап 1 — поиск видео

Пример:

```bash
python youtube_parser.py search --keywords "маркетинг, реклама" --max-results 100 --output search_results.csv
```

Чтобы получить максимально возможное число роликов, используй `0`:

```bash
python youtube_parser.py search --keywords "маркетинг, реклама" --max-results 0 --output search_results.csv
```

Что получится в CSV:
- `title` — название
- `published_at` — дата публикации
- `channel_title` — автор канала
- `view_count` — число просмотров
- `like_count` — число реакций (лайков)
- `comment_count` — число комментариев

Результаты автоматически сортируются по числу просмотров (от большего к меньшему),
чтобы первыми были самые виральные ролики.

## 4. Этап 2 — комментарии

Создай текстовый файл, например `videos.txt`, где каждая строка — ссылка на видео
или его ID (можно смешивать).

Пример содержимого:
```
https://www.youtube.com/watch?v=dQw4w9WgXcQ
dQw4w9WgXcQ
https://youtu.be/9bZkp7q19f0
```

Запуск:

```bash
python youtube_parser.py comments --input videos.txt --top-n 300 --output comments.csv
```

Что получится в CSV:
- `text` — полный текст комментария
- `video_title` — название видео
- `published_at` — дата
- `like_count` — лайки
- `reply_count` — ответы
- `score` — сортировка по лайкам+ответам (чем больше, тем важнее)

## 5. Важно знать
Видео могут быть и длинными, и шортсами — фильтрации по длительности нет.
Если нужно — скажи, добавлю фильтр.

