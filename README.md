## Использование
Замениет `DATABASE_URL` в файле `main.py` на адрес вашей базы данных.

Установите зависимости из файла requirements.txt с помощью команды:
```sh
$ pip install --no-cache-dir -r requirements.txt
```

Запустите с помощью команды:
```sh
$ uvicorn app.main:app
