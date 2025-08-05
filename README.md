# website_auto

Скрипт для автоматического просмотра видео и прохождения тестов на сайте [Otemae ElCampus](https://elcampus.otemae.ac.jp/) университета Otemae.

## Возможности

- Заходит на сайт ElCampus
- Запускает видеоуроки и ждёт их окончания
- Решает тесты с использованием ИИ (Google Gemini 2.0)

## Подготовка

1. Создай виртуальную среду:
```bash
python -m venv venv
```

2. Активируй её:
- Windows:
```bash
source venv\Scripts\activate
```

3. Установи зависимости:
```bash
pip install -r requirements.txt
```

4. Скачай `chromiumdriver` с официального сайта:
https://googlechromelabs.github.io/chrome-for-testing/

5. Разархивируй архив и положи только `chromedriver.exe` в ту же папку, где находится `main.py`.

6. Скрипт работает **только с браузером Chrome**. Убедись, что у тебя установлен Google Chrome соответствующей версии.

7. Создай файл `config.py` на основе `config_example.py`. Там уже прописаны все необходимые инструкции и параметры. Просто скопируй `config_example.py` и переименуй:
```bash
copy config_example.py config.py   # Windows
cp config_example.py config.py     # Linux/macOS
```

8. Если у тебя есть API-ключ для **Google Gemini 2.0**, скрипт будет использовать его для прохождения тестов. Без него эта функция будет недоступна.

## Запуск

```bash
python main.py
```

## Примечания

- Скрипт предназначен только для личного использования.
- Использование ИИ ограничено поддержкой Gemini 2.0.
- Автор не несёт ответственности за возможное нарушение правил платформы ElCampus.
- Автор не предоставляет никаких гарантий. Используйте этот код на свой страх и риск.
