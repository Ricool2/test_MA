import asyncio
import requests

from fastapi import FastAPI, UploadFile, Depends, HTTPException, BackgroundTasks
from starlette.responses import FileResponse
from uuid import UUID, uuid5, NAMESPACE_DNS
from datetime import datetime
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from contextlib import asynccontextmanager

from aiofiles import open as open_async
from os import getcwd, path, mkdir, unlink
from shutil import rmtree

from .models import File, Base

# Создаем асинхронную сессию БД
engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# Функция-инициализатор для приложения
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:

        # Создаем БД по описанным моделям
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all) 

        # Очищаем папку загруженных файлов
        rmtree(path.join(getcwd(), "files")) 
        mkdir(path.join(getcwd(), "files")) 

    yield
    # Освобождаем БД
    await engine.dispose()

app = FastAPI(title="MA_test", lifespan=lifespan)

# Зависимость БД
async def get_session():
    async with async_session() as session:
        yield session 

# Разбиение входных данных по переменным
def store_data(file: UploadFile):
    uid = uuid5(NAMESPACE_DNS, file.filename + datetime.now().isoformat())
    _path = path.join(getcwd(), "files", str(uid))
    model = File(
                uid=uid,
                original_name=file.filename,
                extension=file.filename.split(".")[-1],
                format=file.headers["content-type"],
                size=file.size,
            )
    return uid, _path, model

# Загрузка файлов в облако (на примере Google Drive)
def upload_file_in_cloud(file: File, file_path, chunks: bool = False):

    # Если переключатель активен - файл будет передаваться стримом
    if chunks:
        # Далее спицифика работы с Google Drive Api
        result = requests.post(
            url="https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable",
            headers={
                "X-Upload-Content-Type": file.format,
                "X-Upload-Content-Length": str(file.size),                
            }
        )
        if result.statis_code == 200:
            new_url = result.json()['Location']
            with open(file_path, 'rb') as f:
                while data := file.read(1024):
                    new_req = requests.put(
                        url=new_url,
                        headers={
                            "Content-Length": 1024,
                            "Content-Range": f"bytes 0-1024/{file.size}"
                        },
                        files={
                            "file": (file.original_name, data, file.format)
                        }
                    )
                    if new_req.status_code // 100 == 5:
                        raise Exception(f"Uploading file '{file.original_name}' goes wrong. Response code: {new_req.statis_code}")
    
    else:        
        result = requests.post(
            url="https://www.googleapis.com/upload/drive/v3/files?uploadType=media",
            files={
                'file': (file.original_name, open(file_path, 'rb'), file.format)
            }
        )
        if result.statis_code // 100 != 2:
            raise Exception(f"Uploading file '{file.original_name}' goes wrong. Response code: {result.statis_code}")

# Фоновая задача для удаления файлов через час
async def delete_old_file(uid: UUID, session: AsyncSession, time: int = 3600):
    await asyncio.sleep(time)
    async with session.begin():
        query = delete(File).where(File.uid == uid)
        await session.execute(query)
        unlink(path.join(getcwd(), "files", str(uid)))

@app.post("/stream_upload_files/", status_code=201, description="Запрос на загрузку файлов в стриме")
async def stream_upload_files(files: list[UploadFile], background_task: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    try:
        for file in files:
            uid, _path, file_model = store_data(file)
            async with session.begin():
                session.add(file_model)  
                async with open_async(_path, "wb") as buffer:
                    await asyncio.to_thread(upload_file_in_cloud, file, _path, True)
                    while chunk := await file.read(1024):
                        await buffer.write(chunk)
            background_task.add_task(delete_old_file, uid, session)
    except Exception as e:
        raise HTTPException(400, str(e.orig))

@app.post("/upload_files/", status_code=201, description="Запрос на загрузку файлов целиком")
async def upload_files(files: list[UploadFile], background_task: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    try:
        for file in files:
            uid, _path, file_model = store_data(file)
            async with session.begin():
                session.add(file_model)
                async with open_async(_path, "wb") as f:
                    await asyncio.to_thread(upload_file_in_cloud, file, _path)
                    content = await file.read()
                    await f.write(content)
            background_task.add_task(delete_old_file, uid, session)
    except Exception as e:
        raise HTTPException(400, str(e.orig))

@app.get("/file/", description="Получение фала по его UID")
async def get_file_by_uid(uid: UUID, session: AsyncSession = Depends(get_session)):
    files = await session.execute(
        select(File).where(File.uid == uid)
    )
    result = files.scalars().one()
    return FileResponse(
        path=path.join(getcwd(), "files", str(result.uid)),
        filename=result.original_name,
        media_type=result.format
    )
    
    


        

    