import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from database import (
    init_db,
    add_task,
    get_tasks,
    update_task_status,
    update_task_text,
    update_task_priority,
    update_task_due_datetime
)

from config import TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ------------------------------------------------
# Состояния FSM
# ------------------------------------------------
class TaskState(StatesGroup):
    waiting_for_task_text = State()      # ждём от пользователя текст задачи
    waiting_for_task_priority = State()  # ждём, когда пользователь выберет приоритет (кнопкой)
    waiting_for_task_deadline = State()  # ждём дату/время (или "нет")

    waiting_for_edit_text = State()
    waiting_for_edit_priority = State()
    waiting_for_edit_deadline = State()

# ------------------------------------------------
# Главное меню (ReplyKeyboard)
# ------------------------------------------------
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🆕 Добавить задачу"), KeyboardButton(text="📋 Список активных задач")],
        [KeyboardButton(text="📊 Завершенные и отмененные"), KeyboardButton(text="ℹ️ Помощь")]
    ],
    resize_keyboard=True
)

# ------------------------------------------------
# Старт бота
# ------------------------------------------------
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    text = (
        "Привет! Я бот-планировщик задач. Вот что я умею:\n"
        "- 🆕 Добавлять задачи (с приоритетом по кнопке и дедлайном)\n"
        "- 📋 Показывать список активных задач и редактировать их\n"
        "- 📊 Отображать завершенные и отмененные задачи\n"
        "- ✅ Завершать задачи, ❌ Отменять и т.д.\n"
        "Поехали!"
    )
    await message.answer(text, reply_markup=main_keyboard)

# ------------------------------------------------
# Добавление задачи - шаг 1 (текст)
# ------------------------------------------------
@dp.message(lambda message: message.text == "🆕 Добавить задачу")
async def start_adding_task(message: types.Message, state: FSMContext):
    await message.answer("Введите текст задачи:")
    await state.set_state(TaskState.waiting_for_task_text)

@dp.message(TaskState.waiting_for_task_text)
async def process_task_text(message: types.Message, state: FSMContext):
    task_text = message.text.strip()
    if not task_text:
        await message.answer("⚠️ Текст задачи не может быть пустым! Попробуйте снова.")
        return

    # Сохраняем во временные данные FSM
    await state.update_data(task_text=task_text)

    # Переходим к выбору приоритета через inline-кнопки
    priority_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Высокий",  callback_data="priority_high"),
            InlineKeyboardButton(text="🟡 Средний", callback_data="priority_medium"),
            InlineKeyboardButton(text="🟢 Низкий",  callback_data="priority_low"),
        ]
    ])

    await message.answer("Выберите приоритет задачи:", reply_markup=priority_keyboard)
    await state.set_state(TaskState.waiting_for_task_priority)

# ------------------------------------------------
# Добавление задачи - шаг 2 (приоритет через callback)
# ------------------------------------------------
@dp.callback_query(lambda c: c.data.startswith("priority_"))
async def process_task_priority_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обработка нажатия на одну из кнопок (high/medium/low).
    """
    data = callback_query.data  # например, "priority_high"
    if data == "priority_high":
        priority = "высокий"
    elif data == "priority_medium":
        priority = "средний"
    else:
        priority = "низкий"

    await state.update_data(priority=priority)

    # Сразу переходим к запросу дедлайна
    await callback_query.message.answer(
        "Введите дату и время дедлайна (пример: 25.12.2025 14:30)\n"
        "Или напишите 'нет', если дедлайн не важен."
    )
    await state.set_state(TaskState.waiting_for_task_deadline)

# ------------------------------------------------
# Добавление задачи - шаг 3 (дедлайн)
# ------------------------------------------------
@dp.message(TaskState.waiting_for_task_deadline)
async def process_task_deadline(message: types.Message, state: FSMContext):
    due_input = message.text.strip().lower()
    if due_input == "нет":
        due_datetime_str = ""
    else:
        # Пробуем распарсить дату
        try:
            parsed_dt = datetime.strptime(due_input, "%d.%m.%Y %H:%M")
            due_datetime_str = parsed_dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            await message.answer("⚠️ Неправильный формат даты/времени. Попробуйте еще раз: 25.12.2025 14:30 или 'нет'.")
            return

    # Достаем данные из FSM (текст задачи, приоритет)
    user_data = await state.get_data()
    task_text = user_data["task_text"]
    priority = user_data["priority"]

    # Дата создания (текущая)
    creation_date = datetime.today().strftime('%Y-%m-%d')

    # Сохраняем задачу
    await add_task(
        user_id=message.from_user.id,
        task_text=task_text,
        creation_date=creation_date,
        priority=priority,
        due_datetime=due_datetime_str
    )

    await message.answer("✅ Задача добавлена!", reply_markup=main_keyboard)
    await state.clear()

# ------------------------------------------------
# Просмотр активных задач
# ------------------------------------------------
from aiogram.utils.keyboard import InlineKeyboardBuilder

@dp.message(lambda message: message.text == "📋 Список активных задач")
async def show_tasks(message: types.Message):
    tasks = await get_tasks(message.from_user.id, status="pending")
    if not tasks:
        await message.answer("Нет активных задач.", reply_markup=main_keyboard)
        return

    kb_builder = InlineKeyboardBuilder()

    for t in tasks:
        task_id = t[0]
        task_text = t[1]
        priority  = t[3] or "нет"
        button_text = f"{task_text[:30]}... (приоритет: {priority})"
        # add(Button) добавляет автоматически в новую строку (или в ту же строку, если параметры заданы)
        kb_builder.button(text=button_text, callback_data=f"task_{task_id}")
        kb_builder.adjust(1)  # Выравниваем по одной кнопке в строке

    # kb_builder.as_markup() возвращает объект InlineKeyboardMarkup
    inline_kb = kb_builder.as_markup()

    await message.answer("📋 Выберите задачу для управления:", reply_markup=inline_kb)


# ------------------------------------------------
# Меню управления задачей
# ------------------------------------------------
@dp.callback_query(lambda c: c.data.startswith("task_"))
async def task_action_menu(callback_query: types.CallbackQuery):
    task_id = callback_query.data.split("_")[1]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Текст", callback_data=f"edit_text_{task_id}"),
            InlineKeyboardButton(text="🏷️ Приоритет", callback_data=f"edit_priority_{task_id}"),
            InlineKeyboardButton(text="🗓️ Дедлайн", callback_data=f"edit_deadline_{task_id}")
        ],
        [
            InlineKeyboardButton(text="✅ Завершить", callback_data=f"done_{task_id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{task_id}")
        ]
    ])
    await callback_query.message.edit_text("Выберите действие:", reply_markup=keyboard)

# ------------------------------------------------
# Редактирование текста задачи
# ------------------------------------------------
@dp.callback_query(lambda c: c.data.startswith("edit_text_"))
async def edit_task_text_callback(callback_query: types.CallbackQuery, state: FSMContext):
    task_id = callback_query.data.split("_")[2]
    await state.update_data(task_id=task_id)
    await state.set_state(TaskState.waiting_for_edit_text)
    await callback_query.message.answer("✏️ Введите новый текст для задачи:")

@dp.message(TaskState.waiting_for_edit_text)
async def save_edited_text(message: types.Message, state: FSMContext):
    new_text = message.text.strip()
    if not new_text:
        await message.answer("⚠️ Текст задачи не может быть пустым! Попробуйте еще раз.")
        return

    data = await state.get_data()
    task_id = data["task_id"]
    await update_task_text(task_id, new_text)

    await message.answer("✅ Текст задачи обновлен!", reply_markup=main_keyboard)
    await state.clear()

# ------------------------------------------------
# Редактирование приоритета задачи
# ------------------------------------------------
@dp.callback_query(lambda c: c.data.startswith("edit_priority_"))
async def edit_task_priority_callback(callback_query: types.CallbackQuery, state: FSMContext):
    task_id = callback_query.data.split("_")[2]
    await state.update_data(task_id=task_id)

    # Показываем инлайн-кнопки для выбора приоритета
    priority_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Высокий",  callback_data="setpriority_high"),
            InlineKeyboardButton(text="🟡 Средний", callback_data="setpriority_medium"),
            InlineKeyboardButton(text="🟢 Низкий",  callback_data="setpriority_low"),
        ]
    ])
    await callback_query.message.answer("Выберите новый приоритет:", reply_markup=priority_keyboard)

# Обработчик нажатия на кнопку при редактировании приоритета
@dp.callback_query(lambda c: c.data.startswith("setpriority_"))
async def set_task_priority_callback(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data  # "setpriority_high"/"setpriority_medium"/"setpriority_low"
    if data == "setpriority_high":
        new_priority = "высокий"
    elif data == "setpriority_medium":
        new_priority = "средний"
    else:
        new_priority = "низкий"

    user_data = await state.get_data()
    task_id = user_data["task_id"]

    await update_task_priority(task_id, new_priority)
    await callback_query.message.answer("✅ Приоритет задачи обновлен!", reply_markup=main_keyboard)
    await state.clear()

# ------------------------------------------------
# Редактирование дедлайна
# ------------------------------------------------
@dp.callback_query(lambda c: c.data.startswith("edit_deadline_"))
async def edit_task_deadline_callback(callback_query: types.CallbackQuery, state: FSMContext):
    task_id = callback_query.data.split("_")[2]
    await state.update_data(task_id=task_id)
    await state.set_state(TaskState.waiting_for_edit_deadline)
    await callback_query.message.answer(
        "🗓️ Введите новую дату/время дедлайна (например 25.12.2025 14:30)\n"
        "или напишите 'нет' для удаления дедлайна."
    )

@dp.message(TaskState.waiting_for_edit_deadline)
async def save_edited_deadline(message: types.Message, state: FSMContext):
    due_input = message.text.strip().lower()
    if due_input == "нет":
        due_datetime_str = ""
    else:
        try:
            parsed_dt = datetime.strptime(due_input, "%d.%m.%Y %H:%M")
            due_datetime_str = parsed_dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            await message.answer("⚠️ Неправильный формат. Введите, например: 25.12.2025 14:30 или 'нет'.")
            return

    data = await state.get_data()
    task_id = data["task_id"]

    await update_task_due_datetime(task_id, due_datetime_str)
    await message.answer("✅ Дедлайн задачи обновлен!", reply_markup=main_keyboard)
    await state.clear()

# ------------------------------------------------
# Завершение задачи
# ------------------------------------------------
@dp.callback_query(lambda c: c.data.startswith("done_"))
async def mark_done(callback_query: types.CallbackQuery):
    task_id = callback_query.data.split("_")[1]
    await update_task_status(task_id, "done")
    await callback_query.message.answer("✅ Задача завершена!", reply_markup=main_keyboard)

# ------------------------------------------------
# Отмена задачи
# ------------------------------------------------
@dp.callback_query(lambda c: c.data.startswith("cancel_"))
async def cancel_task(callback_query: types.CallbackQuery):
    task_id = callback_query.data.split("_")[1]
    await update_task_status(task_id, "canceled")
    await callback_query.message.answer("❌ Задача отменена!", reply_markup=main_keyboard)

# ------------------------------------------------
# Просмотр завершенных и отмененных
# ------------------------------------------------
@dp.message(lambda message: message.text == "📊 Завершенные и отмененные")
async def show_completed_and_canceled(message: types.Message):
    done_tasks = await get_tasks(message.from_user.id, status="done", grouped_by_date=True)
    canceled_tasks = await get_tasks(message.from_user.id, status="canceled", grouped_by_date=True)

    if not done_tasks and not canceled_tasks:
        await message.answer("✅❌ У вас нет завершенных или отмененных задач.", reply_markup=main_keyboard)
        return

    text = "📊 Завершенные и отмененные задачи:\n\n"

    # done_tasks и canceled_tasks - это словари вида {date: [...], date: [...]}
    # Где каждая запись - (task_id, text, priority, due)
    for date_key, tasks in sorted(done_tasks.items()):
        text += f"📅 {date_key} (✅ Выполненные):\n"
        for task_id, task_text, priority, due in tasks:
            line = f"  - {task_text}"
            if priority:
                line += f" [Приоритет: {priority}]"
            if due:
                line += f" [Дедлайн: {due}]"
            text += line + "\n"

    for date_key, tasks in sorted(canceled_tasks.items()):
        text += f"\n📅 {date_key} (❌ Отмененные):\n"
        for task_id, task_text, priority, due in tasks:
            line = f"  - {task_text}"
            if priority:
                line += f" [Приоритет: {priority}]"
            if due:
                line += f" [Дедлайн: {due}]"
            text += line + "\n"

    await message.answer(text, reply_markup=main_keyboard)

# ------------------------------------------------
# Запуск бота
# ------------------------------------------------
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
