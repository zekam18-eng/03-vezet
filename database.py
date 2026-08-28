import sqlite3
from datetime import datetime


DB_NAME = "patientnote.db"


# Разделы карты вызова СМП. key — имя столбца в БД, label — заголовок,
# как он подписан на бланке карты. Порядок — как в самой карте.
EMERGENCY_FIELDS = [
    ("complaints", "Жалобы"),
    ("anamnesis", "Анамнез (в т.ч. эпид., аллерг., гинекол. по показаниям)"),
    ("objective_general", "Объективно: общее состояние, сознание, положение, кожные покровы, сыпь, зев, миндалины, лимфоузлы, отёки, t°C"),
    ("breathing", "Органы дыхания"),
    ("circulation", "Органы кровообращения"),
    ("digestion", "Органы пищеварения"),
    ("nervous_system", "Нервная система"),
    ("urogenital", "Мочеполовая система"),
    ("additional_data", "Дополнительные объективные данные"),
    ("local_status", "Локальный статус"),
    ("instrumental_data", "Данные инструментальных исследований (ЭКГ, глюкометрия, пульсоксиметрия и пр.)"),
    ("treatment", "Оказанная помощь и её эффект"),
    ("consumables", "Расходные материалы"),
]

EMERGENCY_FIELD_KEYS = [key for key, _label in EMERGENCY_FIELDS]

EMERGENCY_FIELDS_DDL = ",\n        ".join(f"{key} TEXT" for key in EMERGENCY_FIELD_KEYS)


def connect():
    return sqlite3.connect(DB_NAME)


def create_tables():

    conn = connect()
    cursor = conn.cursor()

    # Заболевания
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diseases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    )
    """)

    # Рекомендации
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        disease_id INTEGER,
        text TEXT,
        FOREIGN KEY(disease_id)
        REFERENCES diseases(id)
    )
    """)

    # Лекарственная информация
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        disease_id INTEGER,
        name TEXT,
        description TEXT,
        FOREIGN KEY(disease_id)
        REFERENCES diseases(id)
    )
    """)

    # Пациенты
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL
    )
    """)

    # Миграция: добавляем дату рождения в уже существующие базы,
    # где столбца ещё нет
    cursor.execute("PRAGMA table_info(patients)")
    patient_columns = [row[1] for row in cursor.fetchall()]
    if "birth_date" not in patient_columns:
        cursor.execute("ALTER TABLE patients ADD COLUMN birth_date TEXT")

    # Назначения (сохранённые памятки конкретного пациента)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prescriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        disease_name TEXT,
        recommendations_text TEXT,
        medicines_text TEXT,
        followup_date TEXT,
        created_at TEXT,
        FOREIGN KEY(patient_id)
        REFERENCES patients(id)
    )
    """)

    # ---------- Карты СМП ----------

    # Диагнозы СМП (со своим списком, отдельным от "Заболеваний" в памятках)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS emergency_diagnoses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mkb_code TEXT
    )
    """)

    # Шаблон карты для диагноза — фиксированный текст по разделам
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS emergency_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        diagnosis_id INTEGER UNIQUE,
        {EMERGENCY_FIELDS_DDL},
        FOREIGN KEY(diagnosis_id)
        REFERENCES emergency_diagnoses(id)
    )
    """)

    # Заполненные карты (по конкретному вызову/пациенту)
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS emergency_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        diagnosis_name TEXT,
        mkb_code TEXT,
        {EMERGENCY_FIELDS_DDL},
        created_at TEXT,
        FOREIGN KEY(patient_id)
        REFERENCES patients(id)
    )
    """)

    conn.commit()
    conn.close()


# ---------- Заболевания ----------

def add_disease(name):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO diseases(name)
        VALUES(?)
        """,
        (name,)
    )

    disease_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return disease_id


def get_diseases():

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name
        FROM diseases
        ORDER BY name
        """
    )

    result = cursor.fetchall()

    conn.close()

    return result


def delete_disease(disease_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM recommendations WHERE disease_id=?", (disease_id,))
    cursor.execute("DELETE FROM medicines WHERE disease_id=?", (disease_id,))
    cursor.execute("DELETE FROM diseases WHERE id=?", (disease_id,))

    conn.commit()
    conn.close()


# ---------- Рекомендации ----------

def add_recommendation(disease_id, text):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO recommendations
        (disease_id, text)
        VALUES (?,?)
        """,
        (disease_id, text)
    )

    recommendation_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return recommendation_id


def get_recommendations(disease_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, text
        FROM recommendations
        WHERE disease_id=?
        ORDER BY id
        """,
        (disease_id,)
    )

    result = cursor.fetchall()

    conn.close()

    return result


def delete_recommendation(recommendation_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM recommendations WHERE id=?", (recommendation_id,))

    conn.commit()
    conn.close()


# ---------- Лекарства ----------

def add_medicine(disease_id, name, description):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO medicines
        (disease_id, name, description)
        VALUES (?,?,?)
        """,
        (disease_id, name, description)
    )

    medicine_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return medicine_id


def get_medicines(disease_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, description
        FROM medicines
        WHERE disease_id=?
        ORDER BY id
        """,
        (disease_id,)
    )

    result = cursor.fetchall()

    conn.close()

    return result


def delete_medicine(medicine_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM medicines WHERE id=?", (medicine_id,))

    conn.commit()
    conn.close()


# ---------- Пациенты ----------

def add_patient(full_name, birth_date=""):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO patients(full_name, birth_date)
        VALUES(?,?)
        """,
        (full_name, birth_date)
    )

    patient_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return patient_id


def get_patients():

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, full_name, birth_date
        FROM patients
        ORDER BY full_name
        """
    )

    result = cursor.fetchall()

    conn.close()

    return result


def delete_patient(patient_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM prescriptions WHERE patient_id=?", (patient_id,))
    cursor.execute("DELETE FROM patients WHERE id=?", (patient_id,))

    conn.commit()
    conn.close()


# ---------- Назначения ----------

def add_prescription(patient_id, disease_name, recommendations_text,
                      medicines_text, followup_date):

    conn = connect()
    cursor = conn.cursor()

    created_at = datetime.now().strftime("%d.%m.%Y %H:%M")

    cursor.execute(
        """
        INSERT INTO prescriptions
        (patient_id, disease_name, recommendations_text, medicines_text,
         followup_date, created_at)
        VALUES (?,?,?,?,?,?)
        """,
        (patient_id, disease_name, recommendations_text, medicines_text,
         followup_date, created_at)
    )

    prescription_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return prescription_id


def get_prescriptions(patient_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, disease_name, followup_date, created_at
        FROM prescriptions
        WHERE patient_id=?
        ORDER BY id DESC
        """,
        (patient_id,)
    )

    result = cursor.fetchall()

    conn.close()

    return result


def get_prescription(prescription_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT pt.full_name, pt.birth_date, p.disease_name, p.recommendations_text,
               p.medicines_text, p.followup_date, p.created_at
        FROM prescriptions p
        JOIN patients pt ON pt.id = p.patient_id
        WHERE p.id=?
        """,
        (prescription_id,)
    )

    result = cursor.fetchone()

    conn.close()

    return result


def delete_prescription(prescription_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM prescriptions WHERE id=?", (prescription_id,))

    conn.commit()
    conn.close()


# ---------- Диагнозы СМП ----------

def add_emergency_diagnosis(name, mkb_code=""):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO emergency_diagnoses(name, mkb_code)
        VALUES(?,?)
        """,
        (name, mkb_code)
    )

    diagnosis_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return diagnosis_id


def get_emergency_diagnoses():

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, mkb_code
        FROM emergency_diagnoses
        ORDER BY name
        """
    )

    result = cursor.fetchall()

    conn.close()

    return result


def update_emergency_diagnosis(diagnosis_id, name, mkb_code):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE emergency_diagnoses
        SET name=?, mkb_code=?
        WHERE id=?
        """,
        (name, mkb_code, diagnosis_id)
    )

    conn.commit()
    conn.close()


def delete_emergency_diagnosis(diagnosis_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM emergency_templates WHERE diagnosis_id=?", (diagnosis_id,))
    cursor.execute("DELETE FROM emergency_diagnoses WHERE id=?", (diagnosis_id,))

    conn.commit()
    conn.close()


# ---------- Шаблоны карт СМП ----------

def get_emergency_template(diagnosis_id):
    """Возвращает словарь {field_key: text} для диагноза.
    Если шаблона ещё нет — все поля пустые строки."""

    conn = connect()
    cursor = conn.cursor()

    columns = ", ".join(EMERGENCY_FIELD_KEYS)

    cursor.execute(
        f"""
        SELECT {columns}
        FROM emergency_templates
        WHERE diagnosis_id=?
        """,
        (diagnosis_id,)
    )

    row = cursor.fetchone()

    conn.close()

    if row is None:
        return {key: "" for key in EMERGENCY_FIELD_KEYS}

    return {key: (value or "") for key, value in zip(EMERGENCY_FIELD_KEYS, row)}


def save_emergency_template(diagnosis_id, fields):
    """Создаёт или обновляет (upsert) шаблон карты для диагноза.
    fields — словарь {field_key: text}."""

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM emergency_templates WHERE diagnosis_id=?",
        (diagnosis_id,)
    )
    existing = cursor.fetchone()

    values = [fields.get(key, "") for key in EMERGENCY_FIELD_KEYS]

    if existing:
        set_clause = ", ".join(f"{key}=?" for key in EMERGENCY_FIELD_KEYS)
        cursor.execute(
            f"UPDATE emergency_templates SET {set_clause} WHERE diagnosis_id=?",
            (*values, diagnosis_id)
        )
    else:
        columns = ", ".join(EMERGENCY_FIELD_KEYS)
        placeholders = ", ".join("?" for _ in EMERGENCY_FIELD_KEYS)
        cursor.execute(
            f"""
            INSERT INTO emergency_templates(diagnosis_id, {columns})
            VALUES(?, {placeholders})
            """,
            (diagnosis_id, *values)
        )

    conn.commit()
    conn.close()


# ---------- Заполненные карты СМП ----------

def add_emergency_card(patient_id, diagnosis_name, mkb_code, fields):
    """Сохраняет заполненную карту вызова.
    fields — словарь {field_key: text}."""

    conn = connect()
    cursor = conn.cursor()

    created_at = datetime.now().strftime("%d.%m.%Y %H:%M")

    columns = ", ".join(EMERGENCY_FIELD_KEYS)
    placeholders = ", ".join("?" for _ in EMERGENCY_FIELD_KEYS)
    values = [fields.get(key, "") for key in EMERGENCY_FIELD_KEYS]

    cursor.execute(
        f"""
        INSERT INTO emergency_cards
        (patient_id, diagnosis_name, mkb_code, {columns}, created_at)
        VALUES (?, ?, ?, {placeholders}, ?)
        """,
        (patient_id, diagnosis_name, mkb_code, *values, created_at)
    )

    card_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return card_id


def get_emergency_cards(patient_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, diagnosis_name, mkb_code, created_at
        FROM emergency_cards
        WHERE patient_id=?
        ORDER BY id DESC
        """,
        (patient_id,)
    )

    result = cursor.fetchall()

    conn.close()

    return result


def get_all_emergency_cards():

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, diagnosis_name, mkb_code, created_at
        FROM emergency_cards
        ORDER BY id DESC
        """
    )

    result = cursor.fetchall()

    conn.close()

    return result


def get_emergency_card(card_id):

    conn = connect()
    cursor = conn.cursor()

    columns = ", ".join(EMERGENCY_FIELD_KEYS)

    cursor.execute(
        f"""
        SELECT diagnosis_name, mkb_code, {columns}, created_at
        FROM emergency_cards
        WHERE id=?
        """,
        (card_id,)
    )

    row = cursor.fetchone()

    conn.close()

    if row is None:
        return None

    diagnosis_name, mkb_code = row[0], row[1]
    field_values = row[2:2 + len(EMERGENCY_FIELD_KEYS)]
    created_at = row[2 + len(EMERGENCY_FIELD_KEYS)]

    fields = {key: (value or "") for key, value in zip(EMERGENCY_FIELD_KEYS, field_values)}

    return diagnosis_name, mkb_code, fields, created_at


def delete_emergency_card(card_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM emergency_cards WHERE id=?", (card_id,))

    conn.commit()
    conn.close()
