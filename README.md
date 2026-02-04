# Техническое задание (ТЗ) на разработку Веб-приложения для управления устройствами MikroTik
1. Название проекта: «MikroTik ITT Central Manager».

2. Цель проекта: Разработать безопасное, отказоустойчивое веб-приложение для централизованного управления конфигурациями, мониторинга состояния и выполнения массовых операций на группе роутеров MikroTik (около 60 устройств).

3. Основные функции:

3.1. Управление подключением к устройствам:

Хранение учетных данных: Безопасное хранение списка всех роутеров (IP/DNS-имя, порт, логин, пароль) в зашифрованном виде.

Группировка устройств: Возможность объединять устройства в группы (например, по клиентам, филиалам, моделям).

Проверка доступности: Автоматическая периодическая проверка доступности устройств (ping, проверка порта API).

3.2. Планировщик задач (Scheduler):

Создание задач: Возможность создавать задачи с выбором: целевое устройство или группа устройств, действие, расписание (однократно, ежедневно, еженедельно, по cron-расписанию).

Типы задач:

Выполнение скрипта: Отправка и выполнение произвольного скрипта на RouterOS.

Массовое изменение правил firewall: Основная задача – работа с адресными списками.

Резервное копирование (Backup): Скачивание и сохранение файлов резервных копий (.backup) и/или конфигураций (.rsc).

Сброс настроек (Reboot/Reset): Плановная перезагрузка устройств.

Логирование результатов: Запись результатов выполнения каждой задачи для каждого устройства (успех, ошибка, вывод команды).

Очередь и асинхронность: Задачи должны выполняться асинхронно, не блокируя интерфейс, с управляемым количеством одновременных подключений к устройствам (например, не более 5-10 одновременно).

3.3. Управление Firewall (основной кейс):

Работа с адресными списками:

Единый белый список (WhiteList): Возможность добавить/удалить домен или IP-адрес в белый список WhiteList. Изменение должно применятся на всех выбранных устройствах.

Единый черный список (BlackList): Аналогично – массовое добавление/удаление записей в список BLAddress.

Просмотр текущих списков: Возможность посмотреть все адреса в этих списках на конкретном устройстве.

Важно: Разработчик должен понять логику существующих правил, особенно правил №6, №12 и разницы между BLAddress (блокировка трафика) и deny-list (блокировка сканеров).

3.4. Резервное копирование (Backup):

Автоматическое создание бэкапов: По расписанию планировщика.

Хранение: Сохранение бэкапов на сервере с веб-приложением с привязкой к дате и устройству.

Восстановление: Возможность загрузить бэкап с сервера и применить его на устройстве (с подтверждением).

4. Технические требования:

Язык и технологии: рекомендуется:

Бэкенд: Python (с библиотеками librouteros или paramiko для SSH). Фреймворк: FastAPI или аналогичный.

Фронтенд: React, Vue.js или современный JavaScript-фреймворк для динамического интерфейса.

База данных: PostgreSQL для хранения данных приложения (задачи, устройства, логи).

Планировщик: Celery (для Python), либо использование системного cron для запуска скриптов.

Безопасность:

Все пароли для доступа к MikroTik должны храниться в зашифрованном виде.

Обязательна аутентификация и авторизация пользователей в самом веб-приложении.

Защита от CSRF, XSS и SQL-инъекций.

Архитектура: Приложение должно быть спроектировано с учетом масштабирования. 60 устройств – не мало, все операции должны быть асинхронными.

4.1. Развертывание и база данных:

- DATABASE_URL обязателен для запуска приложения и миграций.
- Значение по умолчанию — PostgreSQL (пример строки подключения):
  - `postgresql+psycopg2://user:password@localhost:5432/mikrotik_manager`
- В docker-compose переменная DATABASE_URL формируется из DB_USER/DB_PASSWORD/DB_PORT/DB_NAME.
- Локальная разработка: для упрощенной работы можно переопределить DATABASE_URL на SQLite:
  - `DATABASE_URL=sqlite:///./mikrotik_manager.db`
  - это режим только для локальной разработки и тестов.
- Миграции (Alembic):
  - `cd Backend`
  - `alembic revision --autogenerate -m "init"`
  - `alembic upgrade head`

5. Интерфейс пользователя (UI):

Простой и интуитивно понятный веб-интерфейс.

Dashboard с общей статистикой и статусом устройств.

Разделы: "Устройства", "Задачи", "Списки (White/Black)", "Бэкапы".

Возможность выбирать несколько устройств и применять к ним действие.

6. Дополнительные примечания для разработчика:

Правила firewall, которые нужно учесть при разработке функционала работы со списками:

```
 0    ;;; Accept ICMP
      chain=input action=accept protocol=icmp log=no log-prefix="" 

 1    ;;; Accept established,related
      chain=input action=accept connection-state=established,related log=no 
      log-prefix="" 

 2    ;;; Drop Invalid
      chain=input action=drop connection-state=invalid log=no log-prefix="" 

 3    ;;; Allow Connect in LAN
      chain=input action=accept in-interface-list=LAN log=no log-prefix="" 

 4    ;;; drop ALL no Allow_Input
      chain=input action=drop src-address-list=!Allow_Input log=no 
      log-prefix="" 

 5    ;;; Accept established,related
      chain=forward action=accept connection-state=established,related log=no 
      log-prefix="" 

 6    ;;; Drop Invalid
      chain=forward action=drop connection-state=invalid log=no log-prefix="" 

 7    ;;; Accept for IT
      chain=forward action=accept src-address-list=IT_All_Access log=no 
      log-prefix="" 

 8    ;;; Drop BlackList resources
      chain=forward action=drop src-address-list=BlackList log=no log-prefix="" 

 9    ;;; Detect IP Scan
      chain=forward action=add-src-to-address-list protocol=tcp psd=21,5s,3,1 
      src-address-list=!IT_All_Access address-list=Deny_List 
      address-list-timeout=3d log=no log-prefix="" 

10    ;;; Drop ip scaner
      chain=forward action=drop src-address-list=Deny_List log=no log-prefix="" 

11    ;;; All Access for users
      chain=forward action=accept src-address-list=All_Access 
      out-interface-list=WAN log=no log-prefix="" 

12    ;;; Drop all no WhiteList
      chain=forward action=drop dst-address-list=!WhiteList 
      out-interface-list=WAN log=no log-prefix="" 

13    ;;; No routes from wan
      chain=forward action=drop in-interface-list=WAN log=no log-prefix="" 

```

Для работы с API MikroTik рекомендуется использовать именно API-порт (8728 или 8729 для TLS), а не SSH, так как это обычно быстрее и надежнее для автоматизации.

Необходимо предусмотреть промежуточное хранение задач на случай, если устройство в момент выполнения задачи будет недоступно (чтобы повторить попытку позже).
