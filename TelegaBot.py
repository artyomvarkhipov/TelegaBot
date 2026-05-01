import random

from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup

import database

print('Start telegram bot...')

state_storage = StateMemoryStorage()
token_bot = 'ВАШ_ТОКЕН'
bot = TeleBot(token_bot, state_storage=state_storage)

known_users = []
userStep = {}


def show_hint(*lines):
    return '\n'.join(lines)


def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"


class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше ⏭'


class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()
    waiting_for_new_word = State()
    waiting_for_new_translate = State()


def get_user_step(uid):
    if uid in userStep:
        return userStep[uid]
    else:
        known_users.append(uid)
        userStep[uid] = 0
        print("New user detected, who hasn't used \"/start\" yet")
        return 0


@bot.message_handler(commands=['cards', 'start'])
def create_cards(message):
    cid = message.chat.id
    if cid not in known_users:
        known_users.append(cid)
        welcome_msg = (
            "Привет 👋 Давай попрактикуемся в английском языке. "
            "Тренировки можешь проходить в удобном для себя темпе.\n\n"
            "У тебя есть возможность использовать тренажёр, как конструктор, "
            "и собирать свою собственную базу для обучения. Для этого воспользуйся инструментами:\n"
            "добавить слово ➕,\nудалить слово 🔙.\n\nНу что, начнём ⬇️"
        )
        bot.send_message(cid, welcome_msg)
    markup = types.ReplyKeyboardMarkup(row_width=2)

    buttons = []
    word_data = database.get_random_word(cid)
    target_word = word_data[0]  # Берем английское слово
    translate = word_data[1]  # Берем русский перевод
    target_word_btn = types.KeyboardButton(target_word)
    buttons.append(target_word_btn)
    others = database.get_wrong_answers(cid, target_word)
    other_words_btns = [types.KeyboardButton(word) for word in others]
    buttons.extend(other_words_btns)
    random.shuffle(buttons)
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    buttons.extend([next_btn, add_word_btn, delete_word_btn])

    markup.add(*buttons)

    greeting = f"Выбери перевод слова:\n🇷🇺 {translate}"
    bot.send_message(message.chat.id, greeting, reply_markup=markup)
    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate
        data['other_words'] = others


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    bot.delete_state(message.from_user.id, message.chat.id)  # очистка состояния перед созданием новой карточки,
    # чтобы старые данные не мешали новым
    create_cards(message)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        target_word = data['target_word']
        database.delete_user_word(message.chat.id, target_word)
        bot.send_message(message.chat.id, f"Слово {target_word} успешно удалено из твоего словаря!")
    create_cards(message)  # Показываем новую карточку


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word_start(message):
    bot.send_message(message.chat.id, "Введите новое слово на английском:")
    # Переводим пользователя в режим ожидания ввода английского слова
    bot.set_state(message.from_user.id, MyStates.waiting_for_new_word, message.chat.id)


@bot.message_handler(state=MyStates.waiting_for_new_word)
def add_word_en(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['new_word_en'] = message.text
    bot.send_message(message.chat.id, "Введите перевод на русском:")
    # Переводим пользователя в режим ожидания ввода русского перевода
    bot.set_state(message.from_user.id, MyStates.waiting_for_new_translate, message.chat.id)


@bot.message_handler(state=MyStates.waiting_for_new_translate)
def add_word_finish(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        en_word = data['new_word_en']
        ru_word = message.text
        # Сохраняем в базу данных через функцию из database.py
        database.add_user_word(message.chat.id, en_word, ru_word)

    bot.send_message(message.chat.id, f"Слово '{en_word}' успешно добавлено! 🎉")
    # Возвращаем пользователя к карточкам
    create_cards(message)


@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    text = message.text
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        if not data or 'target_word' not in data:
            return bot.send_message(message.chat.id, "Нажмите /start")
        target_word = data['target_word']
        translate_word = data['translate_word']
        other_words = data['other_words']
    if text == target_word:
        hint = show_hint("Отлично!❤", f"{target_word} -> {translate_word}")
        bot.send_message(message.chat.id, hint)
        # Очищаем старое состояние, чтобы create_cards записала новое слово
        bot.delete_state(message.from_user.id, message.chat.id)
        create_cards(message)
    else:
        markup = types.ReplyKeyboardMarkup(row_width=2)
        new_buttons = []
        all_words = [target_word] + other_words

        for word in all_words:
            btn_text = word
            if word == text.replace('❌', ''):
                btn_text += '❌'
            new_buttons.append(types.KeyboardButton(btn_text))
        new_buttons.extend([
            types.KeyboardButton(Command.NEXT),
            types.KeyboardButton(Command.ADD_WORD),
            types.KeyboardButton(Command.DELETE_WORD)
        ])
        hint = show_hint("Допущена ошибка!", f"Попробуй вспомнить слово 🇷🇺{translate_word}")
        markup.add(*new_buttons)
        bot.send_message(message.chat.id, hint, reply_markup=markup)


bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.infinity_polling(skip_pending=True)
