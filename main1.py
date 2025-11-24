from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext

import sqlite3

API_TOKEN = "8350055567:AAH7Ud7QpRs69c1KmjBvoaVXoSoC-sPSO7I"
ADMIN_ID = 7435391786   # sening id

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movies(
        code TEXT PRIMARY KEY,
        name TEXT,
        genre TEXT,
        file_id TEXT,
        info TEXT,
        youtube TEXT
    )
    """)

    conn.commit()
    conn.close()


def save_user(user):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users(user_id, username) VALUES(?,?)",
                   (user.id, user.username))
    conn.commit()
    conn.close()

# ============== STATES =================

class MovieState(StatesGroup):
    name = State()
    code = State()
    genre = State()
    video = State()
    info = State()
    youtube = State()


# ================= START =================

@dp.message_handler(commands=['start'])
async def start(message: types.Message):

    save_user(message.from_user)

    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 Siz ADMINSIZ!\n/addmovie – kino qo‘shish\n/stats – statistika")
    else:
        await message.answer("👋 Kino bazasiga xush kelibsiz!\n/search – kino qidirish")


# ================== ADD MOVIE ==================

@dp.message_handler(commands=['addmovie'])
async def add_movie(message: types.Message):

    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return

    await MovieState.name.set()
    await message.answer("🎬 Kino nomini yozing:")


@dp.message_handler(state=MovieState.name)
async def movie_name(message: types.Message, state: FSMContext):

    await state.update_data(name=message.text)

    await MovieState.next()
    await message.answer("📌 Kino kodini yozing:")


@dp.message_handler(state=MovieState.code)
async def movie_code(message: types.Message, state: FSMContext):

    await state.update_data(code=message.text)

    await MovieState.next()
    await message.answer("🎞 Janrini yozing:")


@dp.message_handler(state=MovieState.genre)
async def movie_genre(message: types.Message, state: FSMContext):

    await state.update_data(genre=message.text)

    await MovieState.next()
    await message.answer("📥 Videoni yoki faylni yuboring:")


@dp.message_handler(content_types=['video','document'], state=MovieState.video)
async def movie_video(message: types.Message, state: FSMContext):

    if message.video:
        file_id = message.video.file_id
    else:
        file_id = message.document.file_id

    await state.update_data(file_id=file_id)

    await MovieState.next()
    await message.answer("📄 Kino haqida ma'lumot yozing:")


@dp.message_handler(state=MovieState.info)
async def movie_info(message: types.Message, state: FSMContext):

    await state.update_data(info=message.text)

    await MovieState.next()
    await message.answer("🔗 YouTube link (bo‘lmasa yo'q deb yoz):")


@dp.message_handler(state=MovieState.youtube)
async def movie_youtube(message: types.Message, state: FSMContext):

    youtube = None if message.text.lower() == "yo'q" else message.text
    await state.update_data(youtube=youtube)

    data = await state.get_data()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO movies 
    VALUES(?,?,?,?,?,?)
    """, (
        data['code'],
        data['name'],
        data['genre'],
        data['file_id'],
        data['info'],
        data['youtube']
    ))

    conn.commit()
    conn.close()

    await message.answer("✅ Kino bazaga saqlandi!")
    await state.finish()


# ================= SEARCH =================

@dp.message_handler(commands=['search'])
async def search_movie(message: types.Message):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    text = message.text.split(maxsplit=1)

    # agar kod yo'q bo‘lsa -> hamma kinolar
    if len(text) == 1:

        cursor.execute("SELECT code,name FROM movies")
        movies = cursor.fetchall()
        conn.close()

        if not movies:
            await message.answer("❌ Hali kino yo‘q")
            return

        kb = types.InlineKeyboardMarkup(row_width=2)

        for code, name in movies:
            kb.insert(types.InlineKeyboardButton(
                text=name, callback_data=f"watch_{code}"
            )) # type: ignore

        await message.answer("🎬 Barcha kinolar:", reply_markup=kb)
        return


    # kod bilan qidirish
    code = text[1]

    cursor.execute("SELECT * FROM movies WHERE code=?", (code,))
    movie = cursor.fetchone()
    conn.close()

    if not movie:
        await message.answer("❌ Kino topilmadi!")
        return

    code, name, genre, file_id, info, youtube = movie

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("▶️ Ko'rish", callback_data=f"watch_{code}")) # type: ignore
    # kb.add(types.InlineKeyboardButton("⬇️ Yuklash", callback_data=f"download_{code}")) # type: ignore

    if youtube:
        kb.add(types.InlineKeyboardButton("📺 YouTube", url=youtube)) # type: ignore

    await message.answer(
        f"🎬 {name}\n\n📌 Kod: {code}\n🎞 Janr: {genre}\n📄 {info}",
        reply_markup=kb
    )


# ================= WATCH =================

@dp.callback_query_handler(lambda c: c.data.startswith("watch_"))
async def watch_movie(callback: types.CallbackQuery):

    code = callback.data.replace("watch_", "")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM movies WHERE code=?", (code,))
    data = cursor.fetchone()
    conn.close()

    if data:
        await callback.message.answer_video(data[0])
    else:
        await callback.message.answer("❌ Topilmadi")


# ================= DOWNLOAD =================

@dp.callback_query_handler(lambda c: c.data.startswith("download_"))
async def download_movie(callback: types.CallbackQuery):

    code = callback.data.replace("download_", "")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM movies WHERE code=?", (code,))
    data = cursor.fetchone()
    conn.close()

    if data:
        await callback.message.answer_document(data[0])
    else:
        await callback.message.answer("❌ Topilmadi")


# ================= STAT =================

@dp.message_handler(commands=['stats'])
async def stats(message: types.Message):

    if message.from_user.id != ADMIN_ID:
        return

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM movies")
    movies = cursor.fetchone()[0]

    conn.close()

    await message.answer(
        f"📊 Statistika:\n\n👤 Foydalanuvchilar: {users}\n🎬 Kinolar: {movies}"
    )


# ============== MAIN =================

if __name__ == "__main__":
    print("Bot ishga tushdi!")
    init_db()
    executor.start_polling(dp, skip_updates=True)
    from main1 import ADMIN_ID
    user = ADMIN_ID

    print(ADMIN_ID)
