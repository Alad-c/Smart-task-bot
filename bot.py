import os
import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Global logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Bot and Dispatcher
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

DATABASE_PATH = "tasks.db"

# --- CORE LOGIC ---

def get_category(text: str) -> str:
    """Determine task category based on keywords."""
    text = text.lower()
    if any(word in text for word in ["study", "lesson", "course", "read"]):
        return "Study"
    elif any(word in text for word in ["buy", "shopping", "store", "price"]):
        return "Shopping"
    return "General"

# --- DATABASE OPERATIONS (ASYNC) ---

async def init_db() -> None:
    """Initialize SQLite database and create the tasks table."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
        )
        await db.commit()
    logger.info("Database initialized successfully")

async def save_task(user_id: int, task: str, category: str) -> None:
    """Save a new task to the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO tasks (user_id, task, category) VALUES (?, ?, ?)",
            (user_id, task, category)
        )
        await db.commit()

async def get_user_tasks(user_id: int) -> list[tuple]:
    """Retrieve all tasks for a specific user."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT id, task, category, created_at FROM tasks WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        return await cursor.fetchall()

async def delete_specific_task(user_id: int, task_id: int) -> None:
    """Delete a task by ID only if it belongs to the user."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
        await db.commit()

async def delete_all_user_tasks(user_id: int) -> None:
    """Clear all tasks for a specific user."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
        await db.commit()

# --- COMMAND HANDLERS ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle /start command and show help menu."""
    welcome_text = (
        "👋 **Welcome to Smart Task Bot!**\n\n"
        "I can help you organize your daily tasks.\n\n"
        "**Available Commands:**\n"
        "📝 *Simply send text* to save it as a task\n"
        "📋 /tasks — View your task list\n"
        "❌ /delete [ID] — Remove a specific task\n"
        "🧹 /clear — Delete all your tasks\n"
        "ℹ️ /start — Show this menu"
    )
    await message.answer(welcome_text, parse_mode="Markdown")

@dp.message(Command("tasks"))
async def cmd_show_tasks(message: types.Message):
    """Display the user's task list."""
    tasks = await get_user_tasks(message.from_user.id)
    if not tasks:
        await message.answer("Your task list is currently empty! 📝")
        return

    response = "📋 **Your Current Tasks:**\n\n"
    for task_id, task, category, created_at in tasks:
        response += f"🆔 `ID: {task_id}` | *{category}*\n📝 {task}\n📅 _{created_at}_\n\n"
    
    await message.answer(response, parse_mode="Markdown")

@dp.message(Command("delete"))
async def cmd_delete_task(message: types.Message):
    """Handle individual task deletion."""
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("⚠ Usage: `/delete [Task ID]` (e.g., `/delete 5`)", parse_mode="Markdown")
        return

    task_id = int(args[1])
    await delete_specific_task(message.from_user.id, task_id)
    await message.answer(f"✅ Task `ID: {task_id}` has been removed.")

@dp.message(Command("clear"))
async def cmd_clear_all(message: types.Message):
    """Handle full list clearing."""
    await delete_all_user_tasks(message.from_user.id)
    await message.answer("🧹 Your task list has been cleared successfully!")

# --- TEXT HANDLER (MUST BE LAST) ---

@dp.message()
async def handle_as_task(message: types.Message):
    """Save any incoming text as a task, ignoring commands."""
    if message.text.startswith("/"):
        return

    category = get_category(message.text)
    await save_task(message.from_user.id, message.text, category)
    await message.reply(f"✅ Saved to **{category}** category.", parse_mode="Markdown")

# --- MAIN EXECUTION ---

async def main():
    """Start the bot."""
    try:
        await init_db()
        logger.info("Bot is online and polling...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
