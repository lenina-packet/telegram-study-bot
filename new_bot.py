import asyncio
import random
import gspread
from aiogram import Bot, Dispatcher, types, Router
from aiogram.types import PollAnswer
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

TOKEN = "7642749376:AAGcsopXgQx0hWMcFVMLG8Cv0VEWYsUS9kc"
ADMIN_USER_ID = 704617782

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("botinfavikusya-52fbe758c9b8.json", scope)
client = gspread.authorize(creds)
spreadsheet = client.open("Bot")
tests_sheet = spreadsheet.worksheet("Тесты")
rating_sheet = spreadsheet.worksheet("Рейтинг")
news_sheet = spreadsheet.worksheet("Рассылки")

session = AiohttpSession()
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()
router = Router()
dp.include_router(router)

active_tests = {}

async def update_user_score(user_id, username, score, test_number):
    user_ids = rating_sheet.col_values(1)
    if str(user_id) in user_ids:
        row_index = user_ids.index(str(user_id)) + 1
        current_score = int(rating_sheet.cell(row_index, 3).value)
        completed_tests = rating_sheet.cell(row_index, 4).value  
        
        if completed_tests:
            completed_tests = completed_tests.split(", ")
            if test_number not in completed_tests:
                completed_tests.append(test_number)
        else:
            completed_tests = [test_number]
        

        rating_sheet.update_cell(row_index, 3, current_score + score)
        rating_sheet.update_cell(row_index, 4, ", ".join(completed_tests))
    else:
        rating_sheet.append_row([str(user_id), username, score, test_number])

async def send_random_test(user_id, username):
    rows = tests_sheet.get_all_values()
    test_numbers = list(set(row[0] for row in rows[1:]))

    user_ids = rating_sheet.col_values(1)
    completed_tests = []

    if str(user_id) in user_ids:
        row_index = user_ids.index(str(user_id)) + 1
        completed_tests = rating_sheet.cell(row_index, 4).value
        if completed_tests:
            completed_tests = completed_tests.split(", ")
        else:
            completed_tests = []

    available_tests = [t for t in test_numbers if t not in completed_tests]

    if not available_tests:
        await bot.send_message(user_id, "Ты уже прошел все доступные тесты! Подожди пока я залью новые задачки к тестикам 😊")
        return

    test_number = random.choice(available_tests)
    test_questions = [row for row in rows if row[0] == test_number]
    random.shuffle(test_questions)

    active_tests[user_id] = {
        "questions": test_questions,
        "correct_answers": 0,
        "answered": 0,
        "username": username,
        "waiting_for_answer": False,
        "test_number": test_number  
    }
    await send_question(user_id)

async def send_question(user_id):
    test_data = active_tests.get(user_id)
    if not test_data or test_data["answered"] >= 8:
        await finish_test(user_id)
        return

    test_data["waiting_for_answer"] = True

    question_data = test_data["questions"][test_data["answered"]]
    question_text = question_data[1]  # Вопрос
    answers = question_data[2:]  # Варианты ответов
    correct_answer = question_data[5]  # Правильный ответ

    random.shuffle(answers)
    correct_index = answers.index(correct_answer)

    test_data["correct_index"] = correct_index

    poll = await bot.send_poll(
        user_id, question_text, answers, type="quiz",
        correct_option_id=correct_index, open_period=60, is_anonymous=False
    )

    test_data["poll_id"] = poll.poll.id

    asyncio.create_task(wait_for_answer(user_id, 60))

async def wait_for_answer(user_id, delay):
    """Ждет ответ пользователя или автоматически переходит к следующему вопросу."""
    await asyncio.sleep(delay)
    test_data = active_tests.get(user_id)

    if test_data and test_data["waiting_for_answer"]:  
        test_data["waiting_for_answer"] = False  
        test_data["answered"] += 1
        await send_question(user_id)  

@router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer):
    user_id = poll_answer.user.id
    test_data = active_tests.get(user_id)

    if not test_data or not test_data["waiting_for_answer"]:
        return 

    test_data["waiting_for_answer"] = False  
    test_data["answered"] += 1

    if poll_answer.option_ids[0] == test_data["correct_index"]:
        test_data["correct_answers"] += 1

    await send_question(user_id)  

async def finish_test(user_id):
    test_data = active_tests.pop(user_id, None)
    if not test_data:
        return

    score = test_data["correct_answers"]
    await update_user_score(user_id, test_data["username"], score, test_data["test_number"])

    levels = ["Новичок (Джуниор)", "Среднячок (Мидл)", "Средне-продвинутый (Мидл+)", "Сеньор"]
    level = levels[min(score // 2, 3)]  # Оценка уровня по баллам

    if level in ["Средне-продвинутый (Мидл+)", "Сеньор"]:
        result_text = (f"Ты молодец! Твой результат {score}/8. Твой уровень: {level} \n\n" 
                       "Предлагаю тебе уже сейчас выбирать вуз, в который ты сможешь поступить на бюджет 🔥\n\n"
                       "Лови файлики с топовыми вузами: ⬇️\n"
                       "[Чек-лист по вузам Санкт-Петербурга!](https://t.me/infa_vikusya/6041) \n"
                       "[Чек-лист по вузам Москвы!](https://t.me/infa_vikusya/6147) \n\n"
                       "Надеюсь, что в этих файликах находится твой вуз мечты ❤️\n\n"
                       "➡️ [Задать любой вопрос по подготовке со мной](http://t.me/predbanmanager_bot?start=telegramlanskayaopis3202501)\n"
                       "➡️ [Больше практики у меня на курсах](http://t.me/predbanmanager_bot?start=telegramlanskayaopis3202501)")
    else:
        result_text = (f"Твой результат {score}/8. Твой уровень: {level} 🫡\n\n"
                   "До ЕГЭ осталось пару месяцев, а твое место на бюджет от тебя убегает! Давай расскажу, как ты можешь за 2 месяца подготовиться к ЕГЭ по Информатике на 80+ баллов 🐸\n\n"
                   "Записывайся на курс ФЛЕШ Финал, в этом курсе я собрала все самое необходимое, чтобы подготовиться к ЕГЭ по Информатике без проблем и за короткое время\n\n"
                   "На картинке выше ты можешь ознакомиться с расписанием курса ⤴️\n\n"
                   "Как я смогу подготовить тебя на 80+ баллов?\n\n"
                   "Я преподаю уже более 6 лет, выпустила 33 120 учеников со средним баллом 83,34, в то время, как в России средний баллов учеников по Информатике составляет 54,3 🚀\n\n"
                   "А также КАЖДЫЙ ДЕСЯТЫЙ СТОБАЛЛЬНИК по Информатике учился у меня 🔥\n\n"
                   "➡️ [Задать любой вопрос по поводу подготовки](http://t.me/predbanmanager_bot?start=telegramlanskayaopis3202501)\n"
                   "➡️ [Записаться на курс ФЛЕШ Финал и сделать результат 8/8](http://t.me/predbanmanager_bot?start=telegramlanskayaopis3202501)")
    
    image_url = "https://i.imgur.com/tjP9i5X.jpeg"  
    await bot.send_photo(user_id, image_url, caption=result_text, parse_mode="Markdown")

@router.message(Command("start"))
async def start_command(message: types.Message):
    welcome_text = "Добро пожаловать! Здесь вы можете пройти тесты и оценить свои знания. Используйте команду /test, чтобы начать тест."
    await bot.send_message(message.from_user.id, welcome_text)

@router.message(Command("test"))
async def test_command(message: types.Message):
    await send_random_test(message.from_user.id, message.from_user.username)

async def update_flag_in_sheet():
    rows = news_sheet.get_all_values()
    for row_index, row in enumerate(rows[1:], start=2): 
        text, date_str, send_flag = row[0], row[1], row[2]

        if send_flag.lower() == 'false' and datetime.strptime(date_str, "%d.%m.%Y").date() == datetime.today().date():
            news_sheet.update_cell(row_index, 3, 'TRUE')
            return row  

    return None  

async def send_newsletter():
    row = await update_flag_in_sheet()
    
    if row is not None:
        text, date, send_flag = row[0], row[1], row[2]
        
        users = rating_sheet.col_values(1) 

        for user in users:
            try:
                await bot.send_message(user, text)
                await asyncio.sleep(0.5) 
            except Exception as e:
                print(f"Ошибка отправки пользователю {user}: {e}")
                
        return "Рассылка отправлена успешно!"
    else:
        return "Нет сообщений для отправки на сегодня."

@router.message(Command("send_newsletter"))
async def send_newsletter_command(message: types.Message):

    if message.from_user.id != ADMIN_USER_ID:
        await bot.send_message(message.from_user.id, "У вас нет прав для отправки рассылки.")
        return

    result = await send_newsletter()

    await bot.send_message(message.from_user.id, result)

async def main():
    dp.poll_answer.register(handle_poll_answer)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
