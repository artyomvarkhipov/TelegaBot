import psycopg2


# Функция для подключения к БД
def get_connection():
    return psycopg2.connect(
        database="english_cards_db",
        user="postgres",
        password="ВАШ_ПАРОЛЬ_ОТ_POSTGRES",
        host="localhost",
        port="5432"
    )


# Функция для создания таблиц и первичного заполнения
def create_db():
    conn = get_connection()
    with conn.cursor() as cur:
        # 1. Создаем таблицу слов
        cur.execute("""
            CREATE TABLE IF NOT EXISTS words (
                id SERIAL PRIMARY KEY,
                target_word VARCHAR(50) UNIQUE NOT NULL,
                translate_word VARCHAR(50) NOT NULL
            );
        """)
        # 2. Создаем таблицу для личных слов пользователей
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_words (
                user_id BIGINT,
                word_id INTEGER REFERENCES words(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, word_id)
            );
        """)

        # 3. Заполняем базу 10 стартовыми словами
        common_words = [
            ('Peace', 'Мир'), ('Green', 'Зеленый'), ('White', 'Белый'),
            ('Hello', 'Привет'), ('Car', 'Машина'), ('Dog', 'Собака'),
            ('Cat', 'Кот'), ('Apple', 'Яблоко'), ('Water', 'Вода'), ('Book', 'Книга')
        ]
        for en, ru in common_words:
            cur.execute("""
                INSERT INTO words (target_word, translate_word)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (en, ru))
    conn.commit()
    conn.close()


# Функция для создания случайного слова из общего словаря + пользователя
def get_random_word(user_id):
    conn = get_connection()
    with conn.cursor() as cur:
        # Запрос выбирает одно случайное слово, которое либо общее (id <= 10),
        # либо привязано к конкретному пользователю в user_words
        cur.execute("""
            SELECT target_word, translate_word FROM words 
            WHERE id <= 10 OR id IN (SELECT word_id FROM user_words WHERE user_id = %s)
            ORDER BY RANDOM() LIMIT 1;
        """, (user_id,))
        word_data = cur.fetchone()  # возвращает одну строку из результата запроса
    conn.close()
    return word_data


# Функция для создания трех случайных неправильных слов для ответа
def get_wrong_answers(user_id, target_word):
    conn = get_connection()
    with conn.cursor() as cur:
        # Запрос берет 3 случайных слова, которые либо общие, либо принадлежат пользователю
        cur.execute("""
            SELECT target_word FROM words 
            WHERE target_word != %s 
            AND (id <= 10 OR id IN (SELECT word_id FROM user_words WHERE user_id = %s))
            ORDER BY RANDOM() LIMIT 3
        """, (target_word, user_id))
        words = [row[0] for row in cur.fetchall()]  # row[0] чтобы получить строку, а не кортеж
    conn.close()
    return words


# Функция для добавления пользователем своего слова в базу
def add_user_word(user_id, target, translate):
    conn = get_connection()
    with conn.cursor() as cur:
        # 1. Добавляем само слово в общий список
        cur.execute("""
            INSERT INTO words (target_word, translate_word)
            VALUES (%s, %s)
            ON CONFLICT (target_word)
            DO UPDATE SET translate_word = EXCLUDED.translate_word
            RETURNING id
        """, (target, translate))
        word_id = cur.fetchone()[0]
        # 2. Привязываем это слово к конкретному пользователю
        cur.execute("""
            INSERT INTO user_words (user_id, word_id) 
            VALUES (%s, %s) 
            ON CONFLICT DO NOTHING
        """, (user_id, word_id))
    conn.commit()
    conn.close()


# Функция для удаления пользователем своего слова
def delete_user_word(user_id, target):
    conn = get_connection()
    with conn.cursor() as cur:
        # Удаляем только связь слова с пользователем (само слово из базы не удаляем)
        cur.execute("""
            DELETE FROM user_words 
            WHERE user_id = %s AND word_id = (SELECT id FROM words WHERE target_word = %s)
        """, (user_id, target))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    try:
        create_db()
        print("Таблицы успешно созданы!")
    except Exception as e:
        print(f"Ошибка при создании: {e}")
