# test_full.py
import random

import requests
import json
import time

BASE_URL = "http://localhost:8000"


def test_api_flow():
    """Полный тест работоспособности API"""
    print("Тестирование MikroTik Manager API")
    print("=" * 50)

    # 1. Проверка доступности
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"✓ API доступен: {response.status_code}")
        print(f"  {response.json()['message']}")
    except Exception as e:
        print(f"✗ Ошибка подключения к API: {e}")
        return

    print("\n1. Тестирование работы с группами:")
    print("-" * 30)

    # 2. Создание группы
    group_data = {
        "name": f"Тестовая группа {random.randint(0,100)}",
        "description": "Группа для тестирования"
    }

    try:
        response = requests.post(
            f"{BASE_URL}/devices/groups/",
            json=group_data
        )
        if response.status_code == 200:
            group_id = response.json()["id"]
            print(f"✓ Группа создана: ID={group_id}")
        else:
            print(f"✗ Ошибка создания группы: {response.status_code}")
            print(f"  Ответ: {response.text}")
            return
    except Exception as e:
        print(f"✗ Ошибка при создании группы: {e}")
        return

    # 3. Получение списка групп
    try:
        response = requests.get(f"{BASE_URL}/devices/groups/")
        print(f"✓ Получено групп: {len(response.json())}")
    except Exception as e:
        print(f"✗ Ошибка получения групп: {e}")

    print("\n2. Тестирование работы с устройствами:")
    print("-" * 30)

    # 4. Создание устройства
    device_data = {
        "name": f"test-router{random.randint(0,100)}",
        "description": "Тестовый MikroTik роутер",
        "host": "192.168.88.1",
        "api_port": 8728,
        "ssh_port": 22,
        "username": "admin",
        "password": "admin",
        "group_id": None,
        "use_ssl": False,
        "check_interval": 300
    }

    try:
        response = requests.post(
            f"{BASE_URL}/devices/",
            json=device_data
        )
        if response.status_code == 200:
            device_id = response.json()["id"]
            print(f"✓ Устройство создано: ID={device_id}")
        else:
            print(f"✗ Ошибка создания устройства: {response.status_code}")
            print(f"  Ответ: {response.text}")
            return
    except Exception as e:
        print(f"✗ Ошибка при создании устройства: {e}")
        return

    # 5. Частичное обновление устройства (привязка к группе)
    update_data = {
        "group_id": group_id
    }

    try:
        response = requests.patch(
            f"{BASE_URL}/devices/{device_id}",
            json=update_data
        )
        if response.status_code == 200:
            print(f"✓ Устройство обновлено (привязано к группе {group_id})")
        else:
            print(f"✗ Ошибка обновления устройства: {response.status_code}")
            print(f"  Ответ: {response.text}")
    except Exception as e:
        print(f"✗ Ошибка при обновлении устройства: {e}")

    # 6. Получение устройства
    try:
        response = requests.get(f"{BASE_URL}/devices/{device_id}")
        if response.status_code == 200:
            device = response.json()
            print(f"✓ Получено устройство: {device['name']}")
            print(f"  Группа: {device['group_id']}")
    except Exception as e:
        print(f"✗ Ошибка получения устройства: {e}")

    # 7. Частичное обновление названия группы
    group_update_data = {
        "name": "Обновленная группа"
    }

    try:
        response = requests.patch(
            f"{BASE_URL}/devices/groups/{group_id}",
            json=group_update_data
        )
        if response.status_code == 200:
            print(f"\n✓ Название группы обновлено")
        else:
            print(f"\n✗ Ошибка обновления группы: {response.status_code}")
            print(f"  Ответ: {response.text}")
    except Exception as e:
        print(f"\n✗ Ошибка при обновлении группы: {e}")

    # 8. Получение группы с устройствами
    try:
        response = requests.get(f"{BASE_URL}/devices/groups/{group_id}")
        if response.status_code == 200:
            group = response.json()
            print(f"✓ Группа: {group['name']}")
            print(f"  Количество устройств: {group['device_count']}")
    except Exception as e:
        print(f"✗ Ошибка получения группы: {e}")

    print("\n3. Проверка статуса устройства:")
    print("-" * 30)

    # 9. Проверка статуса устройства (может занять время)
    try:
        response = requests.get(f"{BASE_URL}/devices/1/status")
        if response.status_code == 200:
            status = response.json()
            print(f"✓ Статус устройства:")
            print(f"  Онлайн: {status['is_online']}")
            print(f"  Доступность API: {status['api_available']}")
            print(f"  Доступность SSH: {status['ssh_available']}")
        else:
            print(f"✗ Ошибка проверки статуса: {response.status_code}")
            print(f"  Ответ: {response.text}")
    except Exception as e:
        print(f"✗ Ошибка при проверке статуса: {e}")

    print("\n" + "=" * 50)
    print("Тестирование завершено!")
    print(f"\nСозданы:")
    print(f"  - Группа: ID={group_id}")
    print(f"  - Устройство: ID={device_id}")
    print(f"\nДокументация API: http://localhost:8000/docs")
    print(f"Список устройств: http://localhost:8000/devices/")
    print(f"Список групп: http://localhost:8000/devices/groups/")


if __name__ == "__main__":
    test_api_flow()