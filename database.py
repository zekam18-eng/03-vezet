import sqlite3
import sys
import os
import shutil
import json
from datetime import datetime


def _resolve_db_path():
    """Определяет путь к рабочей базе данных.

    В обычном запуске (python main.py) — файл рядом со скриптом, как раньше.

    В собранном .exe (PyInstaller) вшитые файлы распаковываются во
    временную папку, которая удаляется при закрытии программы — поэтому
    БД оттуда копируется один раз при первом запуске в постоянную папку
    (%APPDATA%\\03-Vezem на Windows, ~/.03-vezem на прочих
    системах), и дальше приложение работает уже с этой постоянной копией."""

    if getattr(sys, "frozen", False):
        # Папка, куда PyInstaller распаковал вшитые файлы (--add-data)
        bundled_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        bundled_db = os.path.join(bundled_dir, "patientnote.db")

        if sys.platform == "win32":
            base_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "03-Vezem")
        else:
            base_dir = os.path.join(os.path.expanduser("~"), ".03-vezem")

        os.makedirs(base_dir, exist_ok=True)
        persistent_db = os.path.join(base_dir, "patientnote.db")

        if not os.path.exists(persistent_db) and os.path.exists(bundled_db):
            shutil.copyfile(bundled_db, persistent_db)

        return persistent_db

    # Обычный запуск из исходников — поведение как раньше
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "patientnote.db")


DB_NAME = _resolve_db_path()


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


# ============================================================
# Протокол сердечно-лёгочной реанимации (вкладка «Реанимация»)
# Точная структура бумажного/электронного «Протокол СЛР»: разделы,
# справочники (выпадающие списки) для оборудования, и 3 таблицы-
# хронометража (компрессии/ИВЛ, ЭКГ-ритм, медикаменты) по минутам.
# Всё хранится одним JSON-полем protocol_data — см. default_protocol_data().
# ============================================================

DEFIBRILLATOR_MODELS = [
    "Дефибриллятор-монитор ДКИ-Н-10 \"Аксион\"",
    "Дефибриллятор ZOLL R Series",
    "Дефибриллятор ДКИ-Н-08-\"Аксион-Х\"",
    "Дефибриллятор-монитор ДКИн-11",
    "Дефибриллятор LIFEPAK 15",
    "Дефибриллятор Mindray BeneHeart D6",
    "Дефибриллятор Mindray BeneHeart D3",
]

VENTILATOR_MODELS = [
    "Аппарат ИВЛ Oxylog 3000 plus",
    "Аппарат ИВЛ Oxylog 2000 plus",
    "Mindray TV 50",
    "Monnal T60",
    "А-ИВЛ/ВВЛп-3/30 Медпром",
    "Аппарат ИВЛ F120 Mobil",
    "Аппарат ИВЛ OXIVENT OX14 Plus",
    "Аппарат ИВЛ Flight 60",
    "А-ИВЛ/ВВЛп-4/40-Медпром",
    "Аппарат ИВЛ Hamilton-T1",
    "Аппарат ИВЛ LTV",
]

VASCULAR_ACCESS_TIMING_OPTIONS = ["До начала СЛР", "Во время СЛР"]
CLINICAL_DEATH_ONSET_OPTIONS = ["При бригаде СМП", "До бригады СМП"]
RESULT_OPTIONS = ["Успешно", "Неуспешно"]
YES_NO_OPTIONS = ["Да", "Нет"]

# (section_key, заголовок раздела, [(field_key, подпись, тип, [варианты]), ...])
# тип: "text" — обычное поле, "combo" — выпадающий список (со справочником,
# но редактируемый — можно и вписать своё значение).
PROTOCOL_SECTIONS = [
    ("general", "Общие данные", [
        ("last_name", "Фамилия пациента", "text"),
        ("first_name", "Имя", "text"),
        ("patronymic", "Отчество", "text"),
        ("call_date", "Дата приёма вызова", "text"),
        ("substation", "Подстанция", "text"),
        ("brigade", "Бригада", "text"),
    ]),
    ("before_ems", "Реанимация до СМП", [
        ("resuscitation", "Реанимация до СМП", "combo", YES_NO_OPTIONS),
        ("compressions", "Компрессии", "combo", YES_NO_OPTIONS),
        ("ivl", "ИВЛ", "combo", YES_NO_OPTIONS),
    ]),
    ("measures", "Реанимационные мероприятия", [
        ("death_onset", "Наступление клинической смерти", "combo", CLINICAL_DEATH_ONSET_OPTIONS),
        ("death_time", "Время клинической смерти", "text"),
        ("measures_started", "Реаним. мероприятия начаты c", "text"),
    ]),
    ("airway", "Обеспечение проходимости ВДП", [
        ("when", "Когда проводилось", "text"),
        ("suction_time", "Санация ВДП — время выполнения", "text"),
        ("suction_result", "Санация ВДП — результат", "combo", RESULT_OPTIONS),
        ("pharyngeal_time", "Фарингеальный воздуховод — время", "text"),
        ("pharyngeal_result", "Фарингеальный воздуховод — результат", "combo", RESULT_OPTIONS),
        ("pharyngeal_breathing", "Фарингеальный воздуховод — дыхание с 2-х сторон", "combo", YES_NO_OPTIONS),
        ("pharyngeal_excursion", "Фарингеальный воздуховод — экскурсии гр. клетки", "combo", YES_NO_OPTIONS),
        ("sealing_time", "Герметизирующее устройство — время", "text"),
        ("sealing_result", "Герметизирующее устройство — результат", "combo", RESULT_OPTIONS),
        ("sealing_breathing", "Герметизирующее устройство — дыхание с 2-х сторон", "combo", YES_NO_OPTIONS),
        ("sealing_excursion", "Герметизирующее устройство — экскурсии гр. клетки", "combo", YES_NO_OPTIONS),
        ("control_device", "Устройство для контроля реанимации", "combo", YES_NO_OPTIONS),
    ]),
    ("manual_ivl", "Ручная ИВЛ (дыхательный мешок)", [
        ("masochnaya", "Масочная", "text"),
        ("posle_intubatsii", "После интубации/герметизации ВДП", "text"),
        ("oxygen", "Использование кислорода", "text"),
    ]),
    ("apparatus_ivl", "Аппаратная ИВЛ", [
        ("device", "Аппарат", "combo", VENTILATOR_MODELS),
        ("mo", "МО", "text"),
        ("frequency", "Частота", "text"),
        ("fio2", "FiO2", "text"),
        ("time", "Время", "text"),
    ]),
    ("vascular_access", "Сосудистый доступ (выполненный во время СЛР)", [
        ("method", "Обеспечение сосудистого доступа", "combo", VASCULAR_ACCESS_TIMING_OPTIONS),
        ("peripheral_vein", "Периферическая вена", "text"),
        ("peripheral_time", "Периферическая вена — время выполнения", "text"),
        ("peripheral_attempts", "Периферическая вена — количество попыток", "text"),
        ("peripheral_result", "Периферическая вена — результат", "combo", RESULT_OPTIONS),
        ("central_vein", "Центральная вена", "text"),
        ("central_time", "Центральная вена — время выполнения", "text"),
        ("central_attempts", "Центральная вена — количество попыток", "text"),
        ("central_result", "Центральная вена — результат", "combo", RESULT_OPTIONS),
        ("io_access", "Внутрикостный доступ", "text"),
        ("io_time", "Внутрикостный доступ — время выполнения", "text"),
        ("io_attempts", "Внутрикостный доступ — количество попыток", "text"),
        ("io_result", "Внутрикостный доступ — результат", "combo", RESULT_OPTIONS),
    ]),
    ("chronometry_header", "Хронометраж реанимационных мероприятий (минуты от начала СЛР бригадой, оформляющей «Протокол»)", [
        ("start_time", "Время начала СЛР", "text"),
        ("compression_freq", "Частота компрессий гр. клетки", "text"),
        ("compression_auto_device", "Автомат компрессии гр. клетки", "text"),
    ]),
    ("defibrillator_header", "Электрокардиомониторинг", [
        ("device", "Аппарат-дефибриллятор", "combo", DEFIBRILLATOR_MODELS),
    ]),
    ("medication_header", "Медикаментозная поддержка", [
        ("adrenaline_mg", "Адреналин (mg)", "text"),
        ("adrenaline_dilution", "Адреналин — в разведении", "text"),
        ("amiodarone_mg", "Амиодарон (mg)", "text"),
        ("amiodarone_dilution", "Амиодарон — в разведении", "text"),
        ("other1", "Другой препарат 1", "text"),
        ("other2", "Другой препарат 2", "text"),
    ]),
    ("misc", "Дополнительно", [
        ("additional_manipulations", "Дополнительные манипуляции, действия", "text"),
        ("condition_assessment", "Оценка состояния (во время компрессий гр. клетки)", "text"),
        ("special_conditions", "Особые условия реанимационных мероприятий (в т.ч. устранение обратимых причин)", "text"),
    ]),
    ("handover", "Передача пациента", [
        ("brigade_number", "Передан бригаде — номер бригады", "text"),
        ("substation_number", "Передан бригаде — номер подстанции", "text"),
        ("handover_time", "Передан бригаде — время передачи", "text"),
        ("hospital_doctor", "Передан врачу стационара", "text"),
        ("doctor_handover_time", "Передан врачу стационара — время передачи", "text"),
        ("transport_started", "Транспортировка начата", "text"),
    ]),
    ("successful", "Успешная СЛР", [
        ("restore_date", "Восстановл. деятельности — дата", "text"),
        ("restore_time", "Восстановл. деятельности — время", "text"),
        ("glasgow", "Сознание (Глазго)", "text"),
        ("sato2", "SatO2", "text"),
        ("ad", "АД (мм.рт.ст)", "text"),
        ("uzi", "УЗИ", "text"),
        ("pulse", "Пульс (в мин.)", "text"),
        ("kos", "КЩС", "text"),
    ]),
    ("unsuccessful", "Безуспешная СЛР", [
        ("death_date", "Биолог. смерть констатирована — дата", "text"),
        ("death_time", "Биолог. смерть констатирована — время", "text"),
    ]),
    ("crew", "Состав бригады", [
        ("doctor", "Врач", "text"),
        ("paramedic1", "Фельдшер/медсестра", "text"),
        ("paramedic2", "Фельдшер/медсестра", "text"),
    ]),
]

# Таблицы-хронометраж (минуты от начала СЛР). 35 столбцов — как в
# оригинальном протоколе.
PROTOCOL_GRID_COLUMNS_DEFAULT = 35

COMPRESSION_GRID_ROWS = [
    "Компрессии гр.клетки ручные",
    "Компрессии гр. клетки автомат",
    "ИВЛ масочная",
    "ИВЛ после интубации или примен. герметиз. уст-ва",
]

ECG_GRID_ROWS = [
    "Асистолия",
    "Фибрилляция желудочков",
    "Желудочковая тахикардия без пульса",
    "Организованный сердечный ритм без пульса (ЭМД)",
    "Навязанный ритм ЭКС (при использ. ЭКС бригадой)",
    "Организованный сердечный ритм с пульсом",
    "Для детей брадикардия менее 60 в мин.",
    "Для детей сердечный ритм с пульсом более 60 в мин.",
    "Дефибрилляция (указать энергию разряда в Дж.)",
]

MEDICATION_GRID_ROWS = [
    "Адреналин",
    "Амиодарон",
    "Другой препарат 1",
    "Другой препарат 2",
]


def _empty_grid(rows, columns=PROTOCOL_GRID_COLUMNS_DEFAULT):
    return {
        "columns": [str(i) for i in range(1, columns + 1)],
        "cells": [["" for _ in range(columns)] for _ in rows],
    }


def default_protocol_data():
    """Полностью пустой протокол СЛР — все разделы и три таблицы-
    хронометража, готовые к заполнению."""

    data = {}
    for section_key, _title, fields in PROTOCOL_SECTIONS:
        data[section_key] = {f[0]: "" for f in fields}

    data["grid_compressions"] = _empty_grid(COMPRESSION_GRID_ROWS)
    data["grid_ecg"] = _empty_grid(ECG_GRID_ROWS)
    data["grid_meds"] = _empty_grid(MEDICATION_GRID_ROWS)

    return data


# ---------- Локальный статус ----------
# Простая вкладка: диагноз + код МКБ + один текст без подпунктов.
LOCAL_STATUS_FIELDS = [
    ("text", "Локальный статус"),
]


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

    # ---------- Реанимация ----------

    # Случаи реанимации: обычные поля карты вызова (клиническая картина,
    # EMERGENCY_FIELDS) + полный протокол СЛР одним JSON-полем
    # (protocol_data — все разделы + 3 таблицы-хронометража).
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS reanimation_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mkb_code TEXT,
        {EMERGENCY_FIELDS_DDL},
        protocol_data TEXT
    )
    """)

    # ---------- Локальный статус ----------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS local_status_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mkb_code TEXT,
        text TEXT
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


# ---------- Случаи реанимации ----------

def add_reanimation_case(name, mkb_code, clinical_fields=None, protocol_data=None):
    """Создаёт случай реанимации. clinical_fields — словарь
    {field_key: text} по EMERGENCY_FIELD_KEYS (клиническая картина).
    protocol_data — вложенный словарь по PROTOCOL_SECTIONS + 3 таблицы
    (см. default_protocol_data()); если не передан, создаётся полностью
    пустой протокол."""

    conn = connect()
    cursor = conn.cursor()

    if clinical_fields is None:
        clinical_fields = {}
    if protocol_data is None:
        protocol_data = default_protocol_data()

    columns = ", ".join(EMERGENCY_FIELD_KEYS)
    placeholders = ", ".join("?" for _ in EMERGENCY_FIELD_KEYS)
    values = [clinical_fields.get(key, "") for key in EMERGENCY_FIELD_KEYS]

    cursor.execute(
        f"""
        INSERT INTO reanimation_cases(name, mkb_code, {columns}, protocol_data)
        VALUES (?, ?, {placeholders}, ?)
        """,
        (name, mkb_code, *values, json.dumps(protocol_data, ensure_ascii=False))
    )

    case_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return case_id


def update_reanimation_case(case_id, name, mkb_code, clinical_fields, protocol_data):
    """Обновляет существующий случай реанимации целиком (используется
    кнопкой «Сохранить» после правок в форме)."""

    conn = connect()
    cursor = conn.cursor()

    set_clause = ", ".join(f"{key}=?" for key in EMERGENCY_FIELD_KEYS)
    values = [clinical_fields.get(key, "") for key in EMERGENCY_FIELD_KEYS]

    cursor.execute(
        f"""
        UPDATE reanimation_cases
        SET name=?, mkb_code=?, {set_clause}, protocol_data=?
        WHERE id=?
        """,
        (name, mkb_code, *values, json.dumps(protocol_data, ensure_ascii=False), case_id)
    )

    conn.commit()
    conn.close()


def get_reanimation_cases():

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, mkb_code
        FROM reanimation_cases
        ORDER BY id
        """
    )

    result = cursor.fetchall()

    conn.close()

    return result


def get_reanimation_case(case_id):
    """Возвращает (name, mkb_code, clinical_fields, protocol_data)."""

    conn = connect()
    cursor = conn.cursor()

    columns = ", ".join(EMERGENCY_FIELD_KEYS)

    cursor.execute(
        f"""
        SELECT name, mkb_code, {columns}, protocol_data
        FROM reanimation_cases
        WHERE id=?
        """,
        (case_id,)
    )

    row = cursor.fetchone()

    conn.close()

    if row is None:
        return None

    name, mkb_code = row[0], row[1]
    field_values = row[2:2 + len(EMERGENCY_FIELD_KEYS)]
    data_json = row[2 + len(EMERGENCY_FIELD_KEYS)]

    clinical_fields = {key: (value or "") for key, value in zip(EMERGENCY_FIELD_KEYS, field_values)}

    try:
        protocol_data = json.loads(data_json) if data_json else default_protocol_data()
    except (TypeError, ValueError):
        protocol_data = default_protocol_data()

    # На случай, если структура протокола когда-то расширится —
    # подмешиваем недостающие ключи из пустого шаблона, не теряя
    # уже сохранённые данные.
    fresh = default_protocol_data()
    for key, value in fresh.items():
        if key not in protocol_data:
            protocol_data[key] = value
        elif isinstance(value, dict) and isinstance(protocol_data.get(key), dict):
            for sub_key, sub_value in value.items():
                protocol_data[key].setdefault(sub_key, sub_value)

    return name, mkb_code, clinical_fields, protocol_data


def delete_reanimation_case(case_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM reanimation_cases WHERE id=?", (case_id,))

    conn.commit()
    conn.close()


# ---------- Локальный статус ----------

def add_local_status_case(name, mkb_code, text=""):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO local_status_cases(name, mkb_code, text)
        VALUES (?, ?, ?)
        """,
        (name, mkb_code, text)
    )

    case_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return case_id


def get_local_status_cases():

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, mkb_code
        FROM local_status_cases
        ORDER BY name
        """
    )

    result = cursor.fetchall()

    conn.close()

    return result


def get_local_status_case(case_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT name, mkb_code, text
        FROM local_status_cases
        WHERE id=?
        """,
        (case_id,)
    )

    row = cursor.fetchone()

    conn.close()

    if row is None:
        return None

    return row[0], row[1], (row[2] or "")


def update_local_status_text(case_id, text):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE local_status_cases SET text=? WHERE id=?",
        (text, case_id)
    )

    conn.commit()
    conn.close()


def delete_local_status_case(case_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM local_status_cases WHERE id=?", (case_id,))

    conn.commit()
    conn.close()
