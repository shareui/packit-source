# ElyxBuilder

CLI-инструмент для сборки Elyx-плагинов.

## Установка

Воспользуйтесь страницей релизов на GitHub: [shareui/ElyxBuilder/releases](https://github.com/shareui/ElyxBuilder/releases)

## Требования

- Python >= 3.10
- Python 3.11 — нужен только для компиляции `.pyc`
- pyzipper — нужен только для шифрования архивов

---

## Команды

### `elyb --version`

Показывает версию ElyxBuilder.

---

### `elyb new <pluginname> <author>`

Создаёт структуру нового плагина в текущей директории.

```bash
elyb new "My Plugin" myname
elyb new "My Plugin" myname -zf eaf
```

| Аргумент / флаг | Описание |
|---|---|
| `pluginname` | Имя плагина |
| `author` | Идентификатор автора |
| `-zf`, `--zipformat` | Расширение архива (по умолчанию: `eaf`) |

Имя нормализуется для файлов/папок: пробелы убираются с переводом следующего слова в CamelCase, спецсимволы (кроме `_`, `-`, букв и цифр) удаляются. В `meta.yml` имя сохраняется как есть.

ID плагина формируется как `author_PluginName`, максимум 32 символа.

После создания нужно вручную заполнить поле `author` в `meta.yml`.

---

### `elyb build`

Собирает плагин в архив. Запускается из директории с `refmap.yml`.

```bash
elyb build
elyb build -v
elyb build --no-assets
elyb build --ast
elyb build --compile
elyb build --compile --reset
elyb build -p aes-256 mypassword
```

| Флаг | Описание |
|---|---|
| `--no-assets` | Исключить файлы из `optionalAssets` |
| `-v`, `--verbose` | Подробный лог сборки |
| `-a`, `--ast` | Проверить синтаксис `.py` через AST перед сборкой |
| `-c`, `--compile` | Скомпилировать `.py` → `.pyc` (Python 3.11) |
| `-r`, `--reset` | Очистить кэш компиляции перед сборкой (только с `--compile`) |
| `-p METHOD PASS` | Зашифровать архив |

`--ast` и `--compile` взаимоисключающие.

Результат кладётся в `builds/`.

#### Компиляция (`--compile`)

Файлы из `compilationIgnore` не компилируются и попадают в архив как `.py`. Остальные `.py` заменяются скомпилированными `.pyc`. Используется инкрементальный кэш — повторная сборка перекомпилирует только изменённые файлы.

#### Шифрование (`-p`)

Требует: `pip install pyzipper`

| Метод | Описание |
|---|---|
| `zipcrypto` | Стандартное ZIP-шифрование |
| `aes-128` | AES 128-bit |
| `aes-192` | AES 192-bit |
| `aes-256` | AES 256-bit (рекомендуется) |

```bash
elyb build -p aes-256 mypassword
```

---

### `elyb cached`

Показывает, какие файлы изменились с последней компиляции. Запускается из директории с `refmap.yml`.

```bash
elyb cached
```

Требует предварительной сборки с `--compile`.

| Статус | Описание |
|---|---|
| `ok` | Файл не изменён, кэш актуален |
| `modified` | Файл изменился с последней компиляции |
| `new` | Файл ещё не компилировался |
| `ignored` | Файл в `compilationIgnore` |

---

### `elyb add-ignore <path> <target>`

Добавляет путь в один из списков игнорирования в `.elyxbuilder/config.yml`.

```bash
elyb add-ignore "MyPlugin/res/heavy.png" --no-assets
elyb add-ignore "MyPlugin/.elyxbuilder/cache/*" --all
elyb add-ignore "MyPlugin/src/helpers.py" --compile
```

| Флаг | Список | Эффект |
|---|---|---|
| `-a`, `--all` | `ignoreAll` | Исключить из любой сборки |
| `-na`, `--no-assets` | `optionalAssets` | Исключить при `--no-assets` |
| `-c`, `--compile` | `compilationIgnore` | Не компилировать |

Обратные слеши нормализуются в прямые. Дубликаты не добавляются.

---

### `elyb del-ignore <index> <target>`

Удаляет запись из списка игнорирования по индексу (с нуля).

```bash
elyb del-ignore 0 --all
elyb del-ignore 2 --no-assets
elyb del-ignore 1 --compile
```

Флаги те же, что у `add-ignore`. Индекс соответствует позиции в списке в `config.yml`.
