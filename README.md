# packit dev readme

целевая версия elyx: 0.7.6b  
минимальная: 0.7.6b

## structure(src/)

```
packit/src/main.py — точка входа, инициализация всех модулей и линкинг  
packit/src/repom.py — движок конфигурации репозиториев  
packit/src/settings.py — конструктор главного экрана настроек  
packit/src/packlog.py — внутренний API логов  
packit/src/core.py — устаревшее, классы ошибок  
packit/src/ui/install.py — установка плагинов  
packit/src/deeplink/packit.py — главный обработчик перехвата deeplink  
packit/src/deeplink/* — не реализованные диплинки(заглушки)  
packit/src/deeplink/pkill.py — pkill диплинк  
packit/src/chat_ui/button.py — интеграция кнопок управления в интерфейс чата  
packit/src/cfg_comps/contributors.py — вкладка с информацией об авторах проекта  
packit/src/cfg_comps/docs.py — навигация по внешней документации и FAQ  
packit/src/cfg_comps/other.py — прочие параметры  
packit/src/cfg_comps/repos.py — интерфейс добавления и правки репозиториев  
packit/src/cfg_comps/icons.py — меню выбора иконок для репозиториев  
```

разделы настроек должны быть в cfg_comps, интерфейс в чатах в chat_ui

## packlog(логирование)

> для логов использовать только его

внутренний API для логирования в плагине

api находиться по пути `packit/src/packlog.py`

```python
# ПРИМЕР импорта с packit/src
from .packlog import packlog

# ПРИМЕР импорта с packit/src/{любая папка}
from ..packlog import packlog

# добавить info лог
packlog.info("message")

# добавить warning лог
packlog.warn("message")

# добавить error лог
packlog.error("message")

# добавить debug лог
packlog.debug("message")

# добавить текст без времени и уровня
packlog.text("message")

# получить все логи как строку
packlog.get()

# очистить все логи
packlog.clear()
```

планы(не ща): добавить traceback и кастом вывод

логи выводятся в UI через настройки плагина с автообновлением каждые 0.3с
формат лога: `[HH:MM:SS] [LEVEL] message`

strings:
- `empty_logs` - текст при пустых логах
