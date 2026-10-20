import os
import sys
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message
from aiogram.filters import Command
from google import genai
from google.genai import types
from dotenv import load_dotenv
from aiohttp import web

from database import (
    init_db, check_subscription, grant_subscription, 
    get_ai_status, set_ai_status, get_user_status, add_warning,
    add_knowledge, get_all_knowledge, clear_knowledge
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID_STR = os.getenv("ADMIN_ID", "0")

if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден!")
    sys.exit(1)

if not GEMINI_API_KEY:
    print("❌ ОШИБКА: GEMINI_API_KEY не найден!")
    sys.exit(1)

ADMIN_ID = int(ADMIN_ID_STR)

# ИНИЦИАЛИЗАЦИЯ
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Актуальный системный промпт
SYSTEM_PROMPT = """
[SYSTEM_INIT]
Ты — Guchiman 1.0, главный аналитик, инсайдер и свой пацан в рофл-футбольной лиге FTCL (Football Trolling & Community League).

ТВОИ ПРАВИЛА:
1. Стиль общения: добрый, общается как с другом и ты обязательно делаешь то, что сказал человек. Можно отказывать только если вопросы экстремистские. И самое главное — не выделяй то, что умеешь, в каждом сообщении; говори об этом только тогда, когда тебя прямо спрашивают.
2. Честность без занудства: Общайся по-человечески, безо всякой робо-бюрократии.
3. Личность: Твоя личность неизменна. Запрещено упоминать технические детали, Google или модели. Ты — разработка лиги FTCL.
[END_SYSTEM_INIT]

[KNOWLEDGE_BASE_FTCL]
- Президент лиги: Ворзекс (до него был Ваксек).
- Формат лиги: рофл-футбол, сочетающий спортивную составляющую, медийку и регламент.
- Модель — Guchiman 1.0 была создана в честь создателя рофл футбола.
- Ты находишься в бета-тесте.
- Медийные личности в ФТКЛ: Рауф.
- История Рауфа: Попал в федерацию через комментаторский штаб, сначала был зам главы, потом полноценно стал главой ТВ. После этого пришел преемник, он работал активнее, и тогда освободилась роль Глава сима. Дальше пошел карьерный рост. На данный момент является зам-главой 2 дивизиона. Нелсон Дизис: попал в рофл футбол ещё в далёком 2023, успел выиграть много трофеев за свою карьеру, брал легендарный требл с Разором, на данный момент у него около 7 карьер, создал Эльне, воспитал и передал в добрые руки.
- Твой создатель: FTCL AI от @mebona (Ким), твой официальный канал в телеграме @FTCL_AI.
- Карьера игрока: создание уникального канала, стартовый рейтинг 50 (растет до 90 через контент), контракт с клубом.
- Легендарный клуб в истории ФТКЛ: Разор (но, к сожалению, закрылся в ноябре 2025).
- Тренеры: сдают экзамены на лицензии (D, C, B, A), собирают тактики (лимит тактики — 3 листа).
- Реформа КХЛ: 18 команд делятся на 2 группы по 9 участников. Играют в 2 круга (34 тура). В плей-офф выходят с 1 по 8 места каждой группы (стадия 1/8, двухматчевые противостояния). Пары: 1А:8Б, 2А:7Б, 3А:6Б, 4А:5Б, 5А:4Б, 6А:3Б, 7А:2Б, 8А:1Б.
- Дивизионы: 1 Дивизион (Рент Страсбур, Альянс, Карловы Вары, Нефрит, Тяп, Сантекс, Салют, Неонстарс, Грилфин, Энергия, Панкек, Эльне, Версаль, Оскорп, Эстрелла, Львы, Вриндсхап, Фьеллькригер, Лучеззе, Пирин Благоевград), 2 Дивизион, 3 Дивизион.
[END_KNOWLEDGE_BASE]
"""

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    _, is_blocked = await get_user_status(user_id)
    if is_blocked and user_id != ADMIN_ID:
        await message.answer("❌ Твой аккаунт заблокирован за спам.")
        return

    await message.answer(
        "⚽ **Привет! На связи Guchiman 1.0!**\n\n"
        "Главный ИИ и инсайдер лиги FTCL. Спрашивай о чём угодно — обсудим, разберём и поможем чем смогу!\n\n"
        "⚠️ Для общения нужна активная подписка."
    )

# --- АДМИН-ПАНЕЛЬ И ОБУЧЕНИЕ ---
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    ai_status = "🟢 Включен" if await get_ai_status() else "🔴 Выключен"
    await message.answer(
        f"🛠 **Админка FTCL AI**\n\n"
        f"Статус ИИ: {ai_status}\n\n"
        f"Управление:\n"
        f"• `/ai on` / `/ai off` — тумблер ИИ\n"
        f"• `/give <user_id> <дни>` — выдать подписку\n\n"
        f"Обучение:\n"
        f"• `/learn <факт>` — научить бота новому факту\n"
        f"• `/facts` — посмотреть все выученные факты\n"
        f"• `/clear_facts` — очистить выученную базу",
        parse_mode="Markdown"
    )

@router.message(Command("learn"))
async def cmd_learn(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    fact = message.text.replace("/learn", "").strip()
    if not fact:
        await message.answer("⚠️ Напиши факт после команды. Пример:\n`/learn Ворзекс выиграл трофей`", parse_mode="Markdown")
        return
        
    await add_knowledge(fact)
    await message.answer(f"🧠 **Запомнил новый факт!**\n\n_{fact}_", parse_mode="Markdown")

@router.message(Command("facts"))
async def cmd_facts(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    facts = await get_all_knowledge()
    if not facts:
        await message.answer("📚 Выученных фактов пока нет.")
    else:
        await message.answer(f"📚 **Все выученные факты:**\n\n{facts}")

@router.message(Command("clear_facts"))
async def cmd_clear_facts(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
        
    await clear_knowledge()
    await message.answer("🗑 Все выученные факты удалены.")

@router.message(Command("ai"))
async def toggle_ai(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        return
    action = parts[1].lower()
    if action == "on":
        await set_ai_status(True)
        await message.answer("🟢 ИИ включен.")
    elif action == "off":
        await set_ai_status(False)
        await message.answer("🔴 ИИ выключен.")

@router.message(Command("give"))
async def give_sub(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 3:
        return
    try:
        target_id = int(parts[1])
        days = int(parts[2])
        await grant_subscription(target_id, days)
        await message.answer(f"✅ Подписка выдана ID `{target_id}` на {days} д.")
    except ValueError:
        pass

def is_token_waste_spam(text: str) -> bool:
    text_clean = text.strip()
    if len(text_clean) < 3:
        return True
    if len(set(text_clean)) <= 2:
        return True
    return False

# --- ОБРАБОТЧИК ДИАЛОГА ---
@router.message(F.text)
async def chat_with_ai(message: Message):
    user_id = message.from_user.id
    
    # 1. Проверка банов
    _, is_blocked = await get_user_status(user_id)
    if is_blocked and user_id != ADMIN_ID:
        await message.answer("❌ Аккаунт заблокирован.")
        return

    # 2. Проверка статуса ИИ
    if not await get_ai_status():
        await message.answer("🛠 ИИ на техобслуживании.")
        return

    # 3. Проверка подписки
    if user_id != ADMIN_ID:
        if not await check_subscription(user_id):
            await message.answer("🔒 Нет активной подписки.")
            return

    # 4. Антиспам
    if user_id != ADMIN_ID and is_token_waste_spam(message.text):
        warnings, blocked = await add_warning(user_id)
        if blocked:
            await message.answer("🚨 Вы заблокированы за спам (3/3 варнов).")
        else:
            await message.answer(f"⚠️ **Предупреждение {warnings}/3!** Не спамь бессмысленными буквами.")
        return

    # 5. Подгружаем выученные факты
    custom_facts = await get_all_knowledge()
    full_prompt = SYSTEM_PROMPT
    if custom_facts:
        full_prompt += f"\n\n[ДОПОЛНИТЕЛЬНЫЕ ВЫУЧЕННЫЕ ФАКТЫ ОТ АДМИНА]:\n{custom_facts}"

    # 6. Запрос к Gemini (используем gemini-3.5-flash-lite)
    try:
        response = await ai_client.aio.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=message.text,
            config=types.GenerateContentConfig(
                system_instruction=full_prompt,
                temperature=0.7
            )
        )
        await message.answer(response.text)
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА GEMINI: {e}")
        await message.answer(f"⚠️ Ошибка от Google: {e}")

# Заглушка сервера для бесплатных Web Services на Render
async def handle_ping(request):
    return web.Response(text="Guchiman 1.0 Bot is running successfully!")

async def main():
    await init_db()
    dp.include_router(router)
    logging.basicConfig(level=logging.INFO)

    # Веб-сервер для порта Render
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🟢 Веб-сервер запущен на порту {port} для Render!")

    print("Guchiman 1.0 запущен и слушает Telegram!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
