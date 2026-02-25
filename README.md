# packit dev readme

целевая версия elyx: 0.7.8b  
минимальная: 0.7.8b

## structure(src/)

```
packit/src/main.py — точка входа, инициализация всех модулей и линкинг  
packit/src/repom.py — движок конфигурации репозиториев  
packit/src/settings.py — конструктор главного экрана настроек  
packit/src/packlog.py — внутренний API логов  # !!! НЕАКТУАЛЬНО
packit/src/core.py — устаревшее, классы ошибок  
packit/src/ui/install.py — UI установки плагинов, точка входа  
packit/src/ui/loading.py — bottom sheet загрузки  
packit/src/ui/repo.py — bottom sheet выбора репозитория 
packit/src/ui/sort.py — bottom sheet сортировки плагинов  
packit/src/ui/search.py — модуль поиска плагинов  
packit/src/deeplink/packit.py — главный обработчик перехвата deeplink  
packit/src/deeplink/* — обработчики различных deeplink  
packit/src/deeplink/pkill.py — pkill диплинк  
packit/src/deeplink/contributors.py — deeplink для вкладки авторов  
packit/src/deeplink/docs.py — deeplink для документации  
packit/src/deeplink/forum.py — deeplink для форума  
packit/src/deeplink/install.py — deeplink для установки  
packit/src/deeplink/settings.py — deeplink для настроек  
packit/src/deeplink/update.py — deeplink для обновлений  
packit/src/chat_ui/button.py — интеграция кнопок управления в интерфейс чата  
packit/src/cfg_comps/contributors.py — вкладка с информацией об авторах проекта  
packit/src/cfg_comps/docs.py — навигация по внешней документации и FAQ  
packit/src/cfg_comps/other.py — прочие параметры  
packit/src/cfg_comps/repos.py — интерфейс добавления и правки репозиториев  
packit/src/cfg_comps/icons.py — меню выбора иконок для репозиториев  
packit/src/cfg_comps/deeplinks.py — настройка deeplinks  
packit/src/other/copy.py — функция копирования ссылок  
packit/src/other/share.py — функция шаринга файлов  
```

разделы настроек должны быть в cfg_comps, интерфейс в чатах в chat_ui

## логирование

используйте `from android_utils import log`

без всяких приписок по типу [Packit] и тп. а так же без локализации, сугубо на английском

@shareui хули README.md не обновляешь?