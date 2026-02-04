# packit dev readme

целевая версия elyx: 0.7.6b  
минимальная: 0.7.6b

## structure(src/)

```
packit/src/main.py — точка входа, инициализация всех модулей и линкинг
packit/src/repom.py — движок конфигурации репозиториев  
packit/src/settings.py — конструктор главного экрана настроек  
packit/src/core.py — устаревшее, классы ошибок
packit/src/ui/install.py — установка плагинов
packit/src/deeplink/packit.py — главный обработчик перехвата deeplink
packit/src/chat_ui/button.py — интеграция кнопок управления в интерфейс чата
packit/src/cfg_comps/contributors.py — вкладка с информацией об авторах проекта  
packit/src/cfg_comps/docs.py — навигация по внешней документации и FAQ  
packit/src/cfg_comps/other.py — прочие параметры  
packit/src/cfg_comps/repos.py — интерфейс добавления и правки репозиториев  
packit/src/cfg_comps/icons.py — меню выбора иконок для репозиториев  
```

разделы настроек должны быть в cfg_comps, интерфейс в чатах в chat\_ui

> ЗАПОЛНЯТЬ!!!
