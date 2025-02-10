import aiosqlite

DB_NAME = "tasks.db"

async def init_db():
    """Создание таблицы в БД (с добавлением нужных полей).
       Если в реальном проекте таблица уже существует,
       нужно делать миграцию или вручную добавить столбцы.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        # Добавили поля priority, due_datetime
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_text TEXT,
                status TEXT DEFAULT 'pending',
                date TEXT,               -- дата создания (или какая-то рабочая дата)
                priority TEXT,           -- приоритет
                due_datetime TEXT        -- строка с датой/временем дедлайна
            )
        """)
        await db.commit()

async def add_task(user_id: int, task_text: str, creation_date: str, priority: str, due_datetime: str):
    """Добавить новую задачу с датой создания, приоритетом и дедлайном."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO tasks (user_id, task_text, status, date, priority, due_datetime)
            VALUES (?, ?, 'pending', ?, ?, ?)
        """, (user_id, task_text, creation_date, priority, due_datetime))
        await db.commit()

async def get_tasks(user_id: int, status: str, date: str = None, grouped_by_date: bool = False):
    """
    Получить задачи по статусу и (необязательно) конкретной дате создания.
    Если grouped_by_date=True, вернём словарь {дата: [(id, text, priority, due_datetime), ...], ...}
    """
    async with aiosqlite.connect(DB_NAME) as db:
        if date:
            cursor = await db.execute("""
                SELECT id, task_text, date, priority, due_datetime
                FROM tasks
                WHERE user_id = ? AND status = ? AND date = ?
            """, (user_id, status, date))
        else:
            cursor = await db.execute("""
                SELECT id, task_text, date, priority, due_datetime
                FROM tasks
                WHERE user_id = ? AND status = ?
            """, (user_id, status))

        tasks = await cursor.fetchall()

        if grouped_by_date:
            grouped_tasks = {}
            for task in tasks:
                # task = (id, task_text, date, priority, due_datetime)
                task_date = task[2]  # дата (creation_date)
                if task_date not in grouped_tasks:
                    grouped_tasks[task_date] = []
                grouped_tasks[task_date].append((task[0], task[1], task[3], task[4]))
            return grouped_tasks

        return tasks

async def update_task_status(task_id: int, new_status: str):
    """Обновить статус задачи."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE tasks 
            SET status = ? 
            WHERE id = ?
        """, (new_status, task_id))
        await db.commit()

async def update_task_text(task_id: int, new_text: str):
    """Обновить текст задачи."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE tasks
            SET task_text = ?
            WHERE id = ?
        """, (new_text, task_id))
        await db.commit()

async def update_task_priority(task_id: int, new_priority: str):
    """Обновить приоритет задачи."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE tasks
            SET priority = ?
            WHERE id = ?
        """, (new_priority, task_id))
        await db.commit()

async def update_task_due_datetime(task_id: int, new_due: str):
    """Обновить дату/время (дедлайн) задачи."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE tasks
            SET due_datetime = ?
            WHERE id = ?
        """, (new_due, task_id))
        await db.commit()
