import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import init_db, add_task, get_tasks, update_task_status , update_task_text
from config import TOKEN
from datetime import datetime

bot = Bot(token=TOKEN)
dp = Dispatcher()


# Определяем состояния FSM
class TaskState(StatesGroup):
    waiting_for_task_text = State()
    waiting_for_edit_text = State()
    waiting_for_edit_input = State()


# Главное меню (кнопки внизу)
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🆕 Добавить задачу"), KeyboardButton(text="📋 Список активных задач")],
        [KeyboardButton(text="📊 Завершенные и отмененные"), KeyboardButton(text="ℹ️ Помощь")]
    ],
    resize_keyboard=True
)


# Старт бота с приветственным сообщением
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    text = (
        "Привет! Я бот-планировщик задач. Вот что я умею:\n"
        "- 🆕 Добавлять задачи\n"
        "- 📋 Показывать список активных задач\n"
        "- 📊 Отображать завершенные и отмененные задачи\n"
        "- ✏️ Позволяю редактировать, завершать и отменять задачи\n"
        "- 🔄 Позволяю возвращать задачи в работу\n"
    )
    await message.answer(text, reply_markup=main_keyboard)


# Добавление задачи
@dp.message(lambda message: message.text == "🆕 Добавить задачу")
async def ask_task_text(message: types.Message, state: FSMContext):
    await message.answer("Введите текст задачи:")
    await state.set_state(TaskState.waiting_for_task_text)


@dp.message(TaskState.waiting_for_task_text)
async def save_task(message: types.Message, state: FSMContext):
    if not message.text.strip():
        await message.answer("⚠️ Задача не может быть пустой!")
        return

    today = datetime.today().strftime('%Y-%m-%d')
    await add_task(message.from_user.id, message.text, today)
    await message.answer("✅ Задача добавлена!", reply_markup=main_keyboard)
    await state.clear()


# Просмотр активных задач
@dp.message(lambda message: message.text == "📋 Список активных задач")
async def show_tasks(message: types.Message):
    tasks = await get_tasks(message.from_user.id, status="pending")
    if not tasks:
        await message.answer("Нет активных задач.", reply_markup=main_keyboard)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=task[1], callback_data=f"task_{task[0]}")] for task in tasks
    ])

    await message.answer("📋 Выберите задачу для управления:", reply_markup=keyboard)


# Меню управления задачей
@dp.callback_query(lambda c: c.data.startswith("task_"))
async def task_action_menu(callback_query: types.CallbackQuery):
    task_id = callback_query.data.split("_")[1]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_{task_id}")],
        [InlineKeyboardButton(text="✅ Завершить", callback_data=f"done_{task_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{task_id}")]
    ])
    await callback_query.message.edit_text("Выберите действие:", reply_markup=keyboard)


# Редактирование задачи
@dp.callback_query(lambda c: c.data.startswith("edit_"))
async def edit_task(callback_query: types.CallbackQuery, state: FSMContext):
    task_id = callback_query.data.split("_")[1]
    await state.update_data(task_id=task_id)
    await state.set_state(TaskState.waiting_for_edit_text)
    await callback_query.message.answer("✏️ Введите новый текст для задачи:")

@dp.message(TaskState.waiting_for_edit_text)
async def save_edited_task(message: types.Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get("task_id")
    if not message.text.strip():
        await message.answer("⚠️ Текст задачи не может быть пустым!")
        return

    await update_task_text(task_id, message.text)  # Используем новую функцию для обновления текста
    await message.answer("✅ Задача обновлена!", reply_markup=main_keyboard)
    await state.clear()


# Завершение задачи
@dp.callback_query(lambda c: c.data.startswith("done_"))
async def mark_done(callback_query: types.CallbackQuery):
    task_id = callback_query.data.split("_")[1]
    await update_task_status(task_id, "done")
    await callback_query.message.answer("✅ Задача завершена!", reply_markup=main_keyboard)


# Отмена задачи
@dp.callback_query(lambda c: c.data.startswith("cancel_"))
async def cancel_task(callback_query: types.CallbackQuery):
    task_id = callback_query.data.split("_")[1]
    await update_task_status(task_id, "canceled")
    await callback_query.message.answer("❌ Задача отменена!", reply_markup=main_keyboard)


# Просмотр завершенных и отмененных задач
@dp.message(lambda message: message.text == "📊 Завершенные и отмененные")
async def show_completed_and_canceled(message: types.Message):
    done_tasks = await get_tasks(message.from_user.id, status="done", grouped_by_date=True)
    canceled_tasks = await get_tasks(message.from_user.id, status="canceled", grouped_by_date=True)

    if not done_tasks and not canceled_tasks:
        await message.answer("✅❌ У вас нет завершенных или отмененных задач.", reply_markup=main_keyboard)
        return

    text = "📊 Завершенные и отмененные задачи:\n\n"

    for date, tasks in sorted(done_tasks.items()):
        text += f"📅 {date} (✅ Выполненные):\n"
        for task in tasks:
            text += f"  - {task[1]}\n"

    for date, tasks in sorted(canceled_tasks.items()):
        text += f"📅 {date} (❌ Отмененные):\n"
        for task in tasks:
            text += f"  - {task[1]}\n"

    await message.answer(text, reply_markup=main_keyboard)

async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
