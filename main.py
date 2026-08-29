import sys

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QInputDialog,
    QDialog,
    QDialogButtonBox,
    QTextEdit,
    QScrollArea,
)

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

import database as db


class EmergencyCardTab(QWidget):
    """Вкладка «Карта СМП»: по диагнозу (с кодом МКБ) хранится
    фиксированный шаблон заполнения карты вызова (жалобы, анамнез,
    объективно по системам и т.д.), который можно применить к
    конкретному пациенту, поправить и распечатать/сохранить."""

    def __init__(self):
        super().__init__()

        self.current_diagnosis_id = None
        self.current_diagnosis_name = None
        self.current_mkb_code = None

        self.diagnoses = []

        self.field_edits = {}

        self.init_ui()
        self.load_diagnoses()
        self.load_history()

    def init_ui(self):

        # ================= Колонка "Диагнозы" =================

        self.diagnosis_search = QLineEdit()
        self.diagnosis_search.setPlaceholderText("Поиск диагноза...")
        self.diagnosis_search.textChanged.connect(self.filter_diagnoses)

        self.diagnosis_list = QListWidget()
        self.diagnosis_list.itemDoubleClicked.connect(self.open_diagnosis)

        self.open_diagnosis_button = QPushButton("Открыть")
        self.open_diagnosis_button.clicked.connect(self.open_diagnosis)

        self.delete_diagnosis_button = QPushButton("Удалить")
        self.delete_diagnosis_button.clicked.connect(self.delete_selected_diagnosis)

        diagnosis_actions_layout = QHBoxLayout()
        diagnosis_actions_layout.addWidget(self.open_diagnosis_button)
        diagnosis_actions_layout.addWidget(self.delete_diagnosis_button)

        self.add_diagnosis_button = QPushButton("+ Добавить диагноз")
        self.add_diagnosis_button.clicked.connect(self.add_diagnosis)

        self.edit_template_button = QPushButton("Редактировать шаблон карты")
        self.edit_template_button.clicked.connect(self.edit_template)

        history_label = QLabel("Сохранённые карты:")
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self.view_selected_history)

        self.view_history_button = QPushButton("Просмотр / печать")
        self.view_history_button.clicked.connect(self.view_selected_history)

        self.delete_history_button = QPushButton("Удалить запись")
        self.delete_history_button.clicked.connect(self.delete_selected_history)

        history_actions_layout = QHBoxLayout()
        history_actions_layout.addWidget(self.view_history_button)
        history_actions_layout.addWidget(self.delete_history_button)

        diagnosis_layout = QVBoxLayout()
        diagnosis_layout.addWidget(QLabel("Диагнозы (СМП):"))
        diagnosis_layout.addWidget(self.diagnosis_search)
        diagnosis_layout.addWidget(self.diagnosis_list)
        diagnosis_layout.addLayout(diagnosis_actions_layout)
        diagnosis_layout.addWidget(self.add_diagnosis_button)
        diagnosis_layout.addWidget(self.edit_template_button)
        diagnosis_layout.addWidget(history_label)
        diagnosis_layout.addWidget(self.history_list)
        diagnosis_layout.addLayout(history_actions_layout)

        # ================= Колонка "Заполнение карты" =================

        self.diagnosis_title = QLabel("Выберите диагноз")
        self.diagnosis_title.setStyleSheet("font-weight: bold; font-size: 16px;")

        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)

        self.field_edits = {}
        for key, label in db.EMERGENCY_FIELDS:
            field_label = QLabel(label + ":")
            field_label.setStyleSheet("font-weight: bold;")
            text_edit = QTextEdit()
            text_edit.setMinimumHeight(60)
            self.field_edits[key] = text_edit
            form_layout.addWidget(field_label)
            form_layout.addWidget(text_edit)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_container)

        self.save_button = QPushButton("Сохранить карту")
        self.save_button.clicked.connect(self.save_card)

        self.preview_button = QPushButton("Предпросмотр")
        self.preview_button.clicked.connect(self.preview_document)

        self.print_button = QPushButton("Печать")
        self.print_button.clicked.connect(self.print_document)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.preview_button)
        buttons_layout.addWidget(self.print_button)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.diagnosis_title)
        right_layout.addWidget(scroll)
        right_layout.addWidget(self.save_button)
        right_layout.addLayout(buttons_layout)

        # ================= Общая разметка =================

        content = QHBoxLayout()
        content.addLayout(diagnosis_layout, 1)
        content.addLayout(right_layout, 2)

        self.setLayout(content)

    # ==================== Диагнозы ====================

    def load_diagnoses(self):
        db.create_tables()
        self.diagnoses = db.get_emergency_diagnoses()
        self.populate_diagnosis_list(self.diagnoses)

    def populate_diagnosis_list(self, diagnoses):
        self.diagnosis_list.clear()
        for diagnosis_id, name, mkb_code in diagnoses:
            label = f"{name} ({mkb_code})" if mkb_code else name
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, diagnosis_id)
            self.diagnosis_list.addItem(item)

    def filter_diagnoses(self, text):
        text = text.lower().strip()
        if not text:
            self.populate_diagnosis_list(self.diagnoses)
            return
        filtered = [
            d for d in self.diagnoses
            if text in d[1].lower() or text in (d[2] or "").lower()
        ]
        self.populate_diagnosis_list(filtered)

    def open_diagnosis(self):

        selected = self.diagnosis_list.currentItem()

        if not selected:
            QMessageBox.warning(self, "PatientNote", "Выберите диагноз из списка.")
            return

        diagnosis_id = selected.data(Qt.UserRole)
        match = next((d for d in self.diagnoses if d[0] == diagnosis_id), None)
        if match is None:
            return

        _id, name, mkb_code = match

        self.current_diagnosis_id = diagnosis_id
        self.current_diagnosis_name = name
        self.current_mkb_code = mkb_code

        title = f"{name} — код по МКБ: {mkb_code}" if mkb_code else name
        self.diagnosis_title.setText(title)

        template = db.get_emergency_template(diagnosis_id)
        for key, text_edit in self.field_edits.items():
            text_edit.setPlainText(template.get(key, ""))

    def select_and_open_diagnosis(self, diagnosis_id):
        for i in range(self.diagnosis_list.count()):
            item = self.diagnosis_list.item(i)
            if item.data(Qt.UserRole) == diagnosis_id:
                self.diagnosis_list.setCurrentItem(item)
                break
        self.open_diagnosis()

    def delete_selected_diagnosis(self):

        selected = self.diagnosis_list.currentItem()

        if not selected:
            QMessageBox.warning(self, "PatientNote", "Выберите диагноз для удаления.")
            return

        diagnosis_id = selected.data(Qt.UserRole)
        match = next((d for d in self.diagnoses if d[0] == diagnosis_id), None)
        name = match[1] if match else ""

        confirm = QMessageBox.question(
            self,
            "Удаление диагноза",
            f"Удалить диагноз «{name}» вместе с шаблоном карты?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if confirm != QMessageBox.Yes:
            return

        db.delete_emergency_diagnosis(diagnosis_id)

        if self.current_diagnosis_id == diagnosis_id:
            self.current_diagnosis_id = None
            self.current_diagnosis_name = None
            self.current_mkb_code = None
            self.diagnosis_title.setText("Выберите диагноз")
            for text_edit in self.field_edits.values():
                text_edit.clear()

        self.load_diagnoses()

    def add_diagnosis(self):

        name, ok = QInputDialog.getText(self, "Новый диагноз", "Название диагноза:")
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "PatientNote", "Введите название диагноза.")
            return

        mkb_code, ok = QInputDialog.getText(self, "Код по МКБ", "Код по МКБ (необязательно):")
        if not ok:
            mkb_code = ""
        mkb_code = mkb_code.strip()

        diagnosis_id = db.add_emergency_diagnosis(name, mkb_code)

        self.load_diagnoses()
        self.diagnosis_search.setText("")
        self.select_and_open_diagnosis(diagnosis_id)

    def edit_template(self):

        if not self.current_diagnosis_id:
            QMessageBox.warning(self, "PatientNote", "Сначала откройте диагноз.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Шаблон карты — {self.current_diagnosis_name}")
        dialog.resize(700, 800)

        layout = QVBoxLayout(dialog)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)

        template = db.get_emergency_template(self.current_diagnosis_id)
        edits = {}
        for key, label in db.EMERGENCY_FIELDS:
            field_label = QLabel(label + ":")
            field_label.setStyleSheet("font-weight: bold;")
            text_edit = QTextEdit()
            text_edit.setPlainText(template.get(key, ""))
            text_edit.setMinimumHeight(60)
            edits[key] = text_edit
            form_layout.addWidget(field_label)
            form_layout.addWidget(text_edit)

        scroll.setWidget(form_container)
        layout.addWidget(scroll)

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        layout.addWidget(button_box)

        def do_save():
            fields = {key: edit.toPlainText() for key, edit in edits.items()}
            db.save_emergency_template(self.current_diagnosis_id, fields)
            for key, text_edit in self.field_edits.items():
                text_edit.setPlainText(fields.get(key, ""))
            dialog.accept()

        button_box.accepted.connect(do_save)
        button_box.rejected.connect(dialog.reject)

        dialog.exec()

    # ==================== История сохранённых карт ====================

    def load_history(self):
        self.history_list.clear()
        for card_id, diagnosis_name, mkb_code, created_at in db.get_all_emergency_cards():
            label = f"{created_at} — {diagnosis_name}"
            if mkb_code:
                label += f" ({mkb_code})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, card_id)
            self.history_list.addItem(item)

    def save_card(self):

        if not self.current_diagnosis_id:
            QMessageBox.warning(self, "PatientNote", "Сначала откройте диагноз.")
            return

        fields = {key: edit.toPlainText() for key, edit in self.field_edits.items()}

        db.add_emergency_card(
            None,
            self.current_diagnosis_name,
            self.current_mkb_code,
            fields,
        )

        self.load_history()
        QMessageBox.information(self, "PatientNote", "Карта сохранена.")

    def view_selected_history(self):

        item = self.history_list.currentItem()

        if not item:
            QMessageBox.warning(self, "PatientNote", "Выберите запись из истории.")
            return

        card_id = item.data(Qt.UserRole)
        record = db.get_emergency_card(card_id)

        if record is None:
            return

        diagnosis_name, mkb_code, fields, created_at = record

        document = self.build_document_from_record(
            diagnosis_name, mkb_code, fields, created_at
        )
        self.open_editable_note(document)

    def delete_selected_history(self):

        item = self.history_list.currentItem()

        if not item:
            QMessageBox.warning(self, "PatientNote", "Выберите запись для удаления.")
            return

        card_id = item.data(Qt.UserRole)

        confirm = QMessageBox.question(
            self, "Удаление записи",
            "Удалить эту сохранённую карту из истории?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if confirm != QMessageBox.Yes:
            return

        db.delete_emergency_card(card_id)
        self.load_history()

    # ==================== Формирование документа ====================

    def build_document(self):

        fields = {key: edit.toPlainText() for key, edit in self.field_edits.items()}
        created_at = ""

        return self.build_document_from_record(
            self.current_diagnosis_name,
            self.current_mkb_code,
            fields,
            created_at,
        )

    def build_document_from_record(self, diagnosis_name, mkb_code, fields, created_at):

        diagnosis_display = diagnosis_name or "—"
        if mkb_code:
            diagnosis_display += f" (код по МКБ: {mkb_code})"

        sections_html = ""
        for key, label in db.EMERGENCY_FIELDS:
            value = fields.get(key, "") or "—"
            value_html = value.replace("\n", "<br>")
            sections_html += f"<h3>{label}</h3><p>{value_html}</p>"

        header = f"<p><b>Диагноз:</b> {diagnosis_display}</p>"
        if created_at:
            header += f"<p><b>Дата создания карты:</b> {created_at}</p>"

        html = header + sections_html

        document = QTextDocument()
        document.setHtml(html)
        return document

    def validate_before_export(self):

        if not self.current_diagnosis_id:
            QMessageBox.warning(self, "PatientNote", "Сначала откройте диагноз.")
            return False

        return True

    # ==================== Предпросмотр и печать ====================

    def open_editable_note(self, document):

        dialog = QDialog(self)
        dialog.setWindowTitle("Карта — можно отредактировать перед печатью")
        dialog.resize(700, 800)

        text_edit = QTextEdit(dialog)
        text_edit.setDocument(document)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Текст можно свободно менять — правки попадут в печать."))
        layout.addWidget(text_edit)

        buttons_row = QHBoxLayout()

        print_button = QPushButton("Печать")
        close_button = QPushButton("Закрыть")

        buttons_row.addWidget(print_button)
        buttons_row.addWidget(close_button)

        layout.addLayout(buttons_row)

        def do_print():
            printer = QPrinter(QPrinter.HighResolution)
            print_dialog = QPrintDialog(printer, dialog)
            if print_dialog.exec() == QPrintDialog.Accepted:
                text_edit.document().print_(printer)

        print_button.clicked.connect(do_print)
        close_button.clicked.connect(dialog.close)

        dialog.exec()

    def preview_document(self):

        if not self.validate_before_export():
            return

        document = self.build_document()
        self.open_editable_note(document)

    def print_document(self):

        if not self.validate_before_export():
            return

        document = self.build_document()
        self.open_editable_note(document)


class ReanimationTab(QWidget):
    """Вкладка «Реанимация»: список случаев сердечно-лёгочной реанимации.
    У каждого случая — клиническая картина (те же 13 разделов, что и в
    обычной карте СМП) плюс отдельный блок с данными протокола СЛР
    (реанимация до СМП, проходимость ВДП, ИВЛ, сосудистый доступ,
    хронометраж, ЭКГ-мониторинг и дефибрилляция, медикаменты, итог)."""

    def __init__(self):
        super().__init__()

        self.current_case_id = None
        self.current_case_name = None
        self.current_mkb_code = None

        self.cases = []
        self.field_edits = {}

        self.init_ui()
        self.load_cases()

    def init_ui(self):

        # ================= Колонка "Случаи" =================

        self.case_search = QLineEdit()
        self.case_search.setPlaceholderText("Поиск случая...")
        self.case_search.textChanged.connect(self.filter_cases)

        self.case_list = QListWidget()
        self.case_list.itemDoubleClicked.connect(self.open_case)

        self.open_case_button = QPushButton("Открыть")
        self.open_case_button.clicked.connect(self.open_case)

        case_layout = QVBoxLayout()
        case_layout.addWidget(QLabel("Случаи реанимации:"))
        case_layout.addWidget(self.case_search)
        case_layout.addWidget(self.case_list)
        case_layout.addWidget(self.open_case_button)

        # ================= Колонка "Карточка случая" =================

        self.case_title = QLabel("Выберите случай")
        self.case_title.setStyleSheet("font-weight: bold; font-size: 16px;")

        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)

        self.field_edits = {}

        clinical_label = QLabel("Клиническая картина")
        clinical_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 6px;")
        form_layout.addWidget(clinical_label)

        for key, label in db.EMERGENCY_FIELDS:
            field_label = QLabel(label + ":")
            field_label.setStyleSheet("font-weight: bold;")
            text_edit = QTextEdit()
            text_edit.setMinimumHeight(55)
            self.field_edits[key] = text_edit
            form_layout.addWidget(field_label)
            form_layout.addWidget(text_edit)

        protocol_label = QLabel("Протокол сердечно-лёгочной реанимации")
        protocol_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 12px;")
        form_layout.addWidget(protocol_label)

        for key, label in db.REANIMATION_FIELDS:
            field_label = QLabel(label + ":")
            field_label.setStyleSheet("font-weight: bold;")
            text_edit = QTextEdit()
            text_edit.setMinimumHeight(55)
            self.field_edits[key] = text_edit
            form_layout.addWidget(field_label)
            form_layout.addWidget(text_edit)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_container)

        self.preview_button = QPushButton("Предпросмотр")
        self.preview_button.clicked.connect(self.preview_document)

        self.print_button = QPushButton("Печать")
        self.print_button.clicked.connect(self.print_document)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.preview_button)
        buttons_layout.addWidget(self.print_button)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.case_title)
        right_layout.addWidget(scroll)
        right_layout.addLayout(buttons_layout)

        # ================= Общая разметка =================

        content = QHBoxLayout()
        content.addLayout(case_layout, 1)
        content.addLayout(right_layout, 2)

        self.setLayout(content)

    def load_cases(self):
        db.create_tables()
        self.cases = db.get_reanimation_cases()
        self.populate_case_list(self.cases)

    def populate_case_list(self, cases):
        self.case_list.clear()
        for case_id, name, mkb_code in cases:
            label = f"{name} ({mkb_code})" if mkb_code else name
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, case_id)
            self.case_list.addItem(item)

    def filter_cases(self, text):
        text = text.lower().strip()
        if not text:
            self.populate_case_list(self.cases)
            return
        filtered = [
            c for c in self.cases
            if text in c[1].lower() or text in (c[2] or "").lower()
        ]
        self.populate_case_list(filtered)

    def open_case(self):

        selected = self.case_list.currentItem()

        if not selected:
            QMessageBox.warning(self, "PatientNote", "Выберите случай из списка.")
            return

        case_id = selected.data(Qt.UserRole)
        record = db.get_reanimation_case(case_id)

        if record is None:
            return

        name, mkb_code, fields = record

        self.current_case_id = case_id
        self.current_case_name = name
        self.current_mkb_code = mkb_code

        title = f"{name} — код по МКБ: {mkb_code}" if mkb_code else name
        self.case_title.setText(title)

        for key, text_edit in self.field_edits.items():
            text_edit.setPlainText(fields.get(key, ""))

    def build_document(self):

        diagnosis_display = self.current_case_name or "—"
        if self.current_mkb_code:
            diagnosis_display += f" (код по МКБ: {self.current_mkb_code})"

        html = f"<p><b>Случай:</b> {diagnosis_display}</p>"

        html += "<h2>Клиническая картина</h2>"
        for key, label in db.EMERGENCY_FIELDS:
            value = self.field_edits[key].toPlainText() or "—"
            html += f"<h3>{label}</h3><p>{value.replace(chr(10), '<br>')}</p>"

        html += "<h2>Протокол сердечно-лёгочной реанимации</h2>"
        for key, label in db.REANIMATION_FIELDS:
            value = self.field_edits[key].toPlainText() or "—"
            html += f"<h3>{label}</h3><p>{value.replace(chr(10), '<br>')}</p>"

        document = QTextDocument()
        document.setHtml(html)
        return document

    def open_editable_note(self, document):

        dialog = QDialog(self)
        dialog.setWindowTitle("Случай реанимации — можно отредактировать перед печатью")
        dialog.resize(700, 800)

        text_edit = QTextEdit(dialog)
        text_edit.setDocument(document)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Текст можно свободно менять — правки попадут в печать."))
        layout.addWidget(text_edit)

        buttons_row = QHBoxLayout()
        print_button = QPushButton("Печать")
        close_button = QPushButton("Закрыть")
        buttons_row.addWidget(print_button)
        buttons_row.addWidget(close_button)
        layout.addLayout(buttons_row)

        def do_print():
            printer = QPrinter(QPrinter.HighResolution)
            print_dialog = QPrintDialog(printer, dialog)
            if print_dialog.exec() == QPrintDialog.Accepted:
                text_edit.document().print_(printer)

        print_button.clicked.connect(do_print)
        close_button.clicked.connect(dialog.close)

        dialog.exec()

    def preview_document(self):
        if not self.current_case_id:
            QMessageBox.warning(self, "PatientNote", "Сначала откройте случай.")
            return
        self.open_editable_note(self.build_document())

    def print_document(self):
        if not self.current_case_id:
            QMessageBox.warning(self, "PatientNote", "Сначала откройте случай.")
            return
        self.open_editable_note(self.build_document())


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("PatientNote — Карта СМП")
        self.resize(1300, 700)

        tabs = QTabWidget()
        tabs.addTab(EmergencyCardTab(), "Карта СМП")
        tabs.addTab(ReanimationTab(), "Реанимация")

        self.setCentralWidget(tabs)


if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = MainWindow()

    window.show()

    sys.exit(app.exec())
