# packit dev readme

целевая версия elyx: 0.7.6b  
минимальная: 0.7.6b

## structure(src/)

```
packit/src/main.py — точка входа, инициализация всех модулей и линкинг
packit/src/cmds.py — обработчик текстовых команд  
packit/src/repom.py — движок конфигурации репозиториев  
packit/src/settings.py — конструктор главного экрана настроек  
packit/src/core.py — ядро, должна находиться вся логика
packit/src/chat_ui.py — интеграция кнопки управления в интерфейс чата  # переместить в chat_ui/packit.py
packit/src/cfg_comps/command.py — экран со справкой по синтаксису команд  
packit/src/cfg_comps/contributors.py — вкладка с информацией об авторах проекта  
packit/src/cfg_comps/debug.py — инструменты для теста(НЕ ВЫРЕЗАТЬ НА РЕЛИ9АХ)
packit/src/cfg_comps/docs.py — навигация по внешней документации и FAQ  
packit/src/cfg_comps/interface.py — базовы1 GUI для управления плагинами  
packit/src/cfg_comps/other.py — прочие параметры
packit/src/cfg_comps/repos.py — интерфейс добавления и правки репозиториев  
```

> ЗАПОЛНЯТЬ!!!