import aiosqlite

DB_NAME = "tasks.db"

async def init_db():
    """Создание таблицы в БД"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_text TEXT,
                status TEXT DEFAULT 'pending',
                date TEXT
            )
        """)
        await db.commit()

async def add_task(user_id: int, task_text: str, date: str):
    """Добавить новую задачу с датой"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO tasks (user_id, task_text, status, date) VALUES (?, ?, 'pending', ?)", (user_id, task_text, date))
        await db.commit()

async def get_tasks(user_id: int, status: str, date: str = None, grouped_by_date: bool = False):
    """Получить задачи по статусу и дате"""
    async with aiosqlite.connect(DB_NAME) as db:
        if date:
            cursor = await db.execute("SELECT id, task_text, date FROM tasks WHERE user_id = ? AND status = ? AND date = ?", (user_id, status, date))
        else:
            cursor = await db.execute("SELECT id, task_text, date FROM tasks WHERE user_id = ? AND status = ?", (user_id, status))

        tasks = await cursor.fetchall()

        if grouped_by_date:
            grouped_tasks = {}
            for task in tasks:
                task_date = task[2]
                if task_date not in grouped_tasks:
                    grouped_tasks[task_date] = []
                grouped_tasks[task_date].append((task[0], task[1]))
            return grouped_tasks

        return tasks

async def update_task_status(task_id: int, new_status: str):
    """Обновить статус задачи"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
        await db.commit()

async def update_task_text(task_id: int, new_text: str):
    """Обновляет текст задачи"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE tasks SET task_text = ? WHERE id = ?", (new_text, task_id))
        await db.commit()
