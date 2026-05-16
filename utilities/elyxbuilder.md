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

> Все команды запускаются из корня проекта — директории, в которой находится `refmap.yml`.

### `elyb --version`

Показывает версию ElyxBuilder.

---

### `elyb new`

Создаёт структуру нового плагина в текущей директории.

По умолчанию открывается интерактивный режим: для каждого поля `meta.yml` показывается сгенерированное значение в скобках — нажмите Enter, чтобы принять его.

```bash
elyb new
```

С флагом `-g` / `--gen` пропускает интерактивный режим и создаёт плагин сразу по переданным флагам:

```bash
elyb new -g -n "My Plugin" -a myname
elyb new -g -n "My Plugin" -a myname -zf eaf
```

| Флаг | Описание |
|---|---|
| `-g`, `--gen` | Быстрое создание (без интерактивного режима) |
| `-n`, `--name` | Имя плагина (обязательно с `--gen`) |
| `-a`, `--author` | Идентификатор автора (обязательно с `--gen`) |
| `-zf`, `--zipformat` | Расширение архива (по умолчанию: `eaf`, только с `--gen`) |

Имя нормализуется для файлов/папок: пробелы убираются с переводом следующего слова в CamelCase, спецсимволы (кроме `_`, `-`, букв и цифр) удаляются. В `meta.yml` имя сохраняется как есть.

ID плагина формируется как `author_PluginName`, максимум 32 символа.

`description` всегда генерируется автоматически как плейсхолдер `{description}` и не запрашивается.

---

### `elyb build`

Собирает плагин в архив. Запускается из директории с `refmap.yml`.

```bash
elyb build
elyb build -v
elyb build --no-assets
elyb build --no-folder
elyb build --ast
elyb build --compile
elyb build --compile --reset
elyb build -p aes-256 mypassword
elyb build -sv 1.0.0
elyb build -sv 1.0.0 true
elyb build -sc com.example.client
elyb build -sc com.example.client myclient
```

| Флаг | Описание |
|---|---|
| `--no-assets` | Исключить файлы из `optionalAssets` |
| `-nf`, `--no-folder` | Исключить директорию `elyxbuilder` из архива |
| `-v`, `--verbose` | Подробный лог сборки |
| `-a`, `--ast` | Проверить синтаксис `.py` через AST перед сборкой |
| `-c`, `--compile` | Скомпилировать `.py` → `.pyc` (Python 3.11) |
| `-r`, `--reset` | Очистить кэш компиляции перед сборкой (только с `--compile`) |
| `-p METHOD PASS` | Зашифровать архив |
| `-ni`, `--no-info` | Не добавлять блок с информацией elyxbuilder в `meta.yml` |
| `-sv VERSION [APPEND]` | Добавить `static_ver` в блок информации о сборке; необязательный `APPEND=true` добавляет `-{version}` к имени архива (по умолчанию: `false`) |
| `-sc PACKAGE [NAME]` | Добавить `client` в блок информации о сборке; необязательный `NAME` добавляет `-{name}` к имени архива |

`--ast` и `--compile` взаимоисключающие.

Результат кладётся в `builds/`.

#### Информация о сборке

Перед упаковкой elyxbuilder дописывает блок с комментарием в `meta.yml` внутри архива. Файл на диске не изменяется.

```yaml
# elyxbuilder info
compiled: true/false
buildNum: 5
buildDate: 2026-05-09
pythonVer: 3.11
sourceHash: a3f2...
elybVer: 0.3.0
static_ver: "1.0.0"
client: "com.example.client"
```

`static_ver` присутствует только при передаче `-sv` / `--static-version`. Если необязательный второй аргумент равен `true`, к имени архива добавляется `-{version}` (например, `MyPlugin-1.0.0.eaf`).

`client` присутствует только при передаче `-sc` / `--static-client`. Если указан необязательный второй аргумент, к имени архива добавляется `-{name}` (например, `MyPlugin-myclient.eaf`).

Используйте `-ni` / `--no-info`, чтобы пропустить этот блок.

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

---

### `elyb stats builds`

Показывает статистику сборок. Запускается из директории с `refmap.yml`.

```bash
elyb stats builds
```

Пример вывода:

```
Total builds: 10
Uncompiled: 6 (60%)
Compiled: 3 (30%)
Failed: 1 (10%)
```

---

### `elyb stats lines`

Считает строки кода в плагине. Запускается из директории с `refmap.yml`.

```bash
elyb stats lines
```

Считает только `.py` файлы в директории `source` (из `config.yml`). Пример вывода:

```
Lines count statistics for plugin MyPlugin:
MyPlugin/src: 142 (Python only)
```

С флагом `-a` / `--all` считает все не-бинарные файлы в корне плагина и `refmap.yml`:

```bash
elyb stats lines --all
```

Пример вывода:

```
Total lines count statistics for plugin MyPlugin:
.py: 142
.yml: 30
Total: 172
```

С флагом `-add` / `--additional` добавляет дополнительные директории относительно `cwd` (требует `--all`):

```bash
elyb stats lines --all --additional docs scripts
```

| Флаг | Описание |
|---|---|
| `-a`, `--all` | Считать все не-бинарные файлы в корне плагина |
| `-add DIR...`, `--additional DIR...` | Добавить дополнительные директории (требует `--all`) |

---

### `elyb stats size`

Показывает статистику размера файлов. Запускается из директории с `refmap.yml`.

```bash
elyb stats size
```

Показывает суммарный размер `.py` файлов в директории `source` (из `config.yml`). Пример вывода:

```
The size of the directory MyPlugin/src: 4.21 KB (0.0 MB)
Python only
```

С флагом `-a` / `--all` считает все не-бинарные файлы в корне плагина и `refmap.yml`:

```bash
elyb stats size --all
```

Пример вывода:

```
File size statistics for plugin MyPlugin:
.py: 4.21 KB (0.0 MB)
.yml: 0.83 KB (0.0 MB)
```

С флагом `-add` / `--additional` добавляет дополнительные директории относительно `cwd` (требует `--all`):

```bash
elyb stats size --all --additional docs scripts
```

| Флаг | Описание |
|---|---|
| `-a`, `--all` | Считать все не-бинарные файлы в корне плагина |
| `-add DIR...`, `--additional DIR...` | Добавить дополнительные директории (требует `--all`) |

---

### `elyb stats files`

Показывает количество файлов по расширению. Запускается из директории с `refmap.yml`.

```bash
elyb stats files
```

Считает все файлы в корне плагина по расширению. Пример вывода:

```
File count statistics for plugin MyPlugin:
.py: 5
.yml: 3
Total: 8
```

С флагом `-a` / `--all` также включает `refmap.yml`:

```bash
elyb stats files --all
```

С флагом `-add` / `--additional` добавляет дополнительные директории относительно `cwd`:

```bash
elyb stats files --all --additional docs scripts
```

| Флаг | Описание |
|---|---|
| `-a`, `--all` | Включить `refmap.yml` и дополнительные директории |
| `-add DIR...`, `--additional DIR...` | Добавить дополнительные директории (требует `--all`) |
