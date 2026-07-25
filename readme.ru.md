# Telegram Username Checker No Rate Limits

Проверка Telegram юзернеймов через API fragment.com.

## Возможности

- Проверяет занят ли юзернейм или свободен
- Определяет пользователь это или канал
- Показывает DC (дата-центр)
- Показывает наличие аватарки
- Показывает статус Premium
- Проверяет доступность Stars, Premium Gift и Gram
- Показывает статус на маркетплейсе (Sold / On auction / Banned / Unavail)
- Показывает цену продажи и дату покупки для проданных юзернеймов

## Использование

```bash
python3 main.py <username1> [username2 ...]
python3 main.py -f usernames.txt
python3 main.py  # интерактивный режим
```

### Формат файла (`-f`)

Текстовый файл, один юзернейм на строку. С `@` или без:

```
glebxdlol
xieworld_vf
@dsvsfb42
```

## Пример

```bash
python3 main.py glebxdlol xieworld_vf
```

## Контакты автора

- **Автор:** [@glebxdlol](https://t.me/glebxdlol)
- **Канал:** [@xieworld_vf](https://t.me/xieworld_vf)
