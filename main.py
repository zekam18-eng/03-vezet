import sys
import os
import re
import tempfile
import urllib.request
import urllib.error

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
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QGroupBox,
    QFormLayout,
    QSplitter,
)

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView

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

        diagnosis_layout = QVBoxLayout()
        diagnosis_layout.addWidget(QLabel("Диагнозы (СМП):"))
        diagnosis_layout.addWidget(self.diagnosis_search)
        diagnosis_layout.addWidget(self.diagnosis_list)
        diagnosis_layout.addLayout(diagnosis_actions_layout)
        diagnosis_layout.addWidget(self.add_diagnosis_button)
        diagnosis_layout.addWidget(self.edit_template_button)

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
            QMessageBox.warning(self, "03-Везём", "Выберите диагноз из списка.")
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
            QMessageBox.warning(self, "03-Везём", "Выберите диагноз для удаления.")
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
            QMessageBox.warning(self, "03-Везём", "Введите название диагноза.")
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
            QMessageBox.warning(self, "03-Везём", "Сначала откройте диагноз.")
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

    def save_card(self):

        if not self.current_diagnosis_id:
            QMessageBox.warning(self, "03-Везём", "Сначала откройте диагноз.")
            return

        fields = {key: edit.toPlainText() for key, edit in self.field_edits.items()}

        db.add_emergency_card(
            None,
            self.current_diagnosis_name,
            self.current_mkb_code,
            fields,
        )

        QMessageBox.information(self, "03-Везём", "Карта сохранена.")

    # ==================== Предпросмотр и печать ====================

    def build_document(self):

        diagnosis_display = self.current_diagnosis_name or "—"
        if self.current_mkb_code:
            diagnosis_display += f" (код по МКБ: {self.current_mkb_code})"

        sections_html = ""
        for key, label in db.EMERGENCY_FIELDS:
            value = self.field_edits[key].toPlainText() or "—"
            value_html = value.replace("\n", "<br>")
            sections_html += f"<h3>{label}</h3><p>{value_html}</p>"

        html = f"<p><b>Диагноз:</b> {diagnosis_display}</p>" + sections_html

        document = QTextDocument()
        document.setHtml(html)
        return document

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
        if not self.current_diagnosis_id:
            QMessageBox.warning(self, "03-Везём", "Сначала откройте диагноз.")
            return
        self.open_editable_note(self.build_document())

    def print_document(self):
        if not self.current_diagnosis_id:
            QMessageBox.warning(self, "03-Везём", "Сначала откройте диагноз.")
            return
        self.open_editable_note(self.build_document())


class ReanimationTab(QWidget):
    """Вкладка «Реанимация»: список случаев сердечно-лёгочной реанимации.
    У каждого случая — клиническая картина (те же 13 разделов, что и в
    обычной карте СМП) и полный протокол СЛР, повторяющий структуру
    реального бланка «Протокол СЛР»: разделы с полями и справочниками
    (выпадающими списками для оборудования) и три таблицы-хронометража
    по минутам (компрессии/ИВЛ, ЭКГ-ритм, медикаменты)."""

    def __init__(self):
        super().__init__()

        self.current_case_id = None
        self.current_case_name = None
        self.current_mkb_code = None

        self.cases = []
        self.field_edits = {}
        self.protocol_widgets = {}  # (section_key, field_key) -> QLineEdit/QComboBox
        self.grid_compressions = None
        self.grid_ecg = None
        self.grid_meds = None

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

        self.delete_case_button = QPushButton("Удалить")
        self.delete_case_button.clicked.connect(self.delete_selected_case)

        case_actions_layout = QHBoxLayout()
        case_actions_layout.addWidget(self.open_case_button)
        case_actions_layout.addWidget(self.delete_case_button)

        self.add_case_button = QPushButton("+ Добавить случай")
        self.add_case_button.clicked.connect(self.add_case)

        case_layout = QVBoxLayout()
        case_layout.addWidget(QLabel("Случаи реанимации:"))
        case_layout.addWidget(self.case_search)
        case_layout.addWidget(self.case_list)
        case_layout.addLayout(case_actions_layout)
        case_layout.addWidget(self.add_case_button)

        # ================= Колонка "Карточка случая" =================

        self.case_title = QLabel("Выберите случай")
        self.case_title.setStyleSheet("font-weight: bold; font-size: 16px;")

        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)

        # ---- Клиническая картина (те же поля, что в "Карте СМП") ----

        clinical_box = QGroupBox("Клиническая картина")
        clinical_layout = QVBoxLayout(clinical_box)
        self.field_edits = {}
        for key, label in db.EMERGENCY_FIELDS:
            field_label = QLabel(label + ":")
            field_label.setStyleSheet("font-weight: bold;")
            text_edit = QTextEdit()
            text_edit.setMinimumHeight(50)
            self.field_edits[key] = text_edit
            clinical_layout.addWidget(field_label)
            clinical_layout.addWidget(text_edit)
        form_layout.addWidget(clinical_box)

        # ---- Протокол СЛР: разделы по db.PROTOCOL_SECTIONS ----

        protocol_title = QLabel("Протокол сердечно-лёгочной реанимации")
        protocol_title.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 10px;")
        form_layout.addWidget(protocol_title)

        self.protocol_widgets = {}

        for section_key, section_title, section_fields in db.PROTOCOL_SECTIONS:
            box = QGroupBox(section_title)
            box_form = QFormLayout(box)
            box_form.setLabelAlignment(Qt.AlignLeft)

            for spec in section_fields:
                field_key, field_label = spec[0], spec[1]
                field_type = spec[2]

                if field_type == "combo":
                    options = spec[3]
                    widget = QComboBox()
                    widget.setEditable(True)
                    widget.addItem("")
                    widget.addItems(options)
                else:
                    widget = QLineEdit()

                self.protocol_widgets[(section_key, field_key)] = widget
                box_form.addRow(field_label + ":", widget)

            form_layout.addWidget(box)

            # Таблицы-хронометража вставляются сразу после нужного раздела
            if section_key == "chronometry_header":
                grid_label = QLabel("Хронометраж (компрессии, ИВЛ) — по минутам:")
                grid_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
                form_layout.addWidget(grid_label)
                self.grid_compressions = QTableWidget()
                self.grid_compressions.setRowCount(len(db.COMPRESSION_GRID_ROWS))
                self.grid_compressions.setVerticalHeaderLabels(db.COMPRESSION_GRID_ROWS)
                self.grid_compressions.setMinimumHeight(140)
                form_layout.addWidget(self.grid_compressions)

            if section_key == "defibrillator_header":
                grid_label = QLabel("Ритм / дефибрилляция — по минутам:")
                grid_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
                form_layout.addWidget(grid_label)
                self.grid_ecg = QTableWidget()
                self.grid_ecg.setRowCount(len(db.ECG_GRID_ROWS))
                self.grid_ecg.setVerticalHeaderLabels(db.ECG_GRID_ROWS)
                self.grid_ecg.setMinimumHeight(280)
                form_layout.addWidget(self.grid_ecg)

            if section_key == "medication_header":
                grid_label = QLabel("Медикаменты — по минутам:")
                grid_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
                form_layout.addWidget(grid_label)
                self.grid_meds = QTableWidget()
                self.grid_meds.setRowCount(len(db.MEDICATION_GRID_ROWS))
                self.grid_meds.setVerticalHeaderLabels(db.MEDICATION_GRID_ROWS)
                self.grid_meds.setMinimumHeight(140)
                form_layout.addWidget(self.grid_meds)

        self.add_minute_button = QPushButton("+ Добавить минуту (во все таблицы)")
        self.add_minute_button.clicked.connect(self.add_grid_column)
        form_layout.addWidget(self.add_minute_button)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_container)

        self.save_button = QPushButton("Сохранить случай")
        self.save_button.clicked.connect(self.save_case)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.case_title)
        right_layout.addWidget(scroll)
        right_layout.addWidget(self.save_button)

        # ================= Общая разметка =================

        content = QHBoxLayout()
        content.addLayout(case_layout, 1)
        content.addLayout(right_layout, 2)

        self.setLayout(content)

    # ==================== Случаи ====================

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
            QMessageBox.warning(self, "03-Везём", "Выберите случай из списка.")
            return

        case_id = selected.data(Qt.UserRole)
        record = db.get_reanimation_case(case_id)

        if record is None:
            return

        name, mkb_code, clinical_fields, protocol_data = record

        self.current_case_id = case_id
        self.current_case_name = name
        self.current_mkb_code = mkb_code

        title = f"{name} — код по МКБ: {mkb_code}" if mkb_code else name
        self.case_title.setText(title)

        for key, text_edit in self.field_edits.items():
            text_edit.setPlainText(clinical_fields.get(key, ""))

        self.load_protocol(protocol_data)

    def add_case(self):

        name, ok = QInputDialog.getText(self, "Новый случай", "Название/диагноз случая:")
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "03-Везём", "Введите название случая.")
            return

        mkb_code, ok = QInputDialog.getText(self, "Код по МКБ", "Код по МКБ (необязательно):")
        if not ok:
            mkb_code = ""
        mkb_code = mkb_code.strip()

        empty_clinical = {key: "" for key in db.EMERGENCY_FIELD_KEYS}
        case_id = db.add_reanimation_case(name, mkb_code, empty_clinical, db.default_protocol_data())

        self.load_cases()
        self.case_search.setText("")
        self.select_and_open_case(case_id)

    def select_and_open_case(self, case_id):
        for i in range(self.case_list.count()):
            item = self.case_list.item(i)
            if item.data(Qt.UserRole) == case_id:
                self.case_list.setCurrentItem(item)
                break
        self.open_case()

    def delete_selected_case(self):

        selected = self.case_list.currentItem()

        if not selected:
            QMessageBox.warning(self, "03-Везём", "Выберите случай для удаления.")
            return

        case_id = selected.data(Qt.UserRole)
        match = next((c for c in self.cases if c[0] == case_id), None)
        name = match[1] if match else ""

        confirm = QMessageBox.question(
            self, "Удаление случая",
            f"Удалить случай «{name}»?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if confirm != QMessageBox.Yes:
            return

        db.delete_reanimation_case(case_id)

        if self.current_case_id == case_id:
            self.current_case_id = None
            self.current_case_name = None
            self.current_mkb_code = None
            self.case_title.setText("Выберите случай")
            for text_edit in self.field_edits.values():
                text_edit.clear()
            self.load_protocol(db.default_protocol_data())

        self.load_cases()

    def save_case(self):

        if not self.current_case_id:
            QMessageBox.warning(self, "03-Везём", "Сначала откройте или добавьте случай.")
            return

        clinical_fields = {key: edit.toPlainText() for key, edit in self.field_edits.items()}
        protocol_data = self.collect_protocol()

        db.update_reanimation_case(
            self.current_case_id,
            self.current_case_name,
            self.current_mkb_code,
            clinical_fields,
            protocol_data,
        )

        self.load_cases()
        QMessageBox.information(self, "03-Везём", "Случай сохранён.")

    # ==================== Протокол СЛР: разделы + таблицы ====================

    def load_protocol(self, protocol_data):

        for (section_key, field_key), widget in self.protocol_widgets.items():
            value = protocol_data.get(section_key, {}).get(field_key, "")
            if isinstance(widget, QComboBox):
                widget.setCurrentText(value)
            else:
                widget.setText(value)

        self._load_grid(self.grid_compressions, protocol_data.get("grid_compressions"), db.COMPRESSION_GRID_ROWS)
        self._load_grid(self.grid_ecg, protocol_data.get("grid_ecg"), db.ECG_GRID_ROWS)
        self._load_grid(self.grid_meds, protocol_data.get("grid_meds"), db.MEDICATION_GRID_ROWS)

    def _load_grid(self, table, grid, row_labels):
        if grid is None:
            grid = db._empty_grid(row_labels)

        columns = grid.get("columns", [])
        cells = grid.get("cells", [])

        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)

        for row_idx in range(len(row_labels)):
            row_values = cells[row_idx] if row_idx < len(cells) else []
            for col_idx in range(len(columns)):
                value = row_values[col_idx] if col_idx < len(row_values) else ""
                table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def collect_protocol(self):

        protocol_data = {}
        for section_key, _title, fields in db.PROTOCOL_SECTIONS:
            protocol_data[section_key] = {}
            for spec in fields:
                field_key = spec[0]
                widget = self.protocol_widgets[(section_key, field_key)]
                if isinstance(widget, QComboBox):
                    protocol_data[section_key][field_key] = widget.currentText()
                else:
                    protocol_data[section_key][field_key] = widget.text()

        protocol_data["grid_compressions"] = self._collect_grid(self.grid_compressions)
        protocol_data["grid_ecg"] = self._collect_grid(self.grid_ecg)
        protocol_data["grid_meds"] = self._collect_grid(self.grid_meds)

        return protocol_data

    def _collect_grid(self, table):
        columns = []
        for col_idx in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(col_idx)
            columns.append(header_item.text() if header_item else str(col_idx + 1))

        cells = []
        for row_idx in range(table.rowCount()):
            row_values = []
            for col_idx in range(table.columnCount()):
                item = table.item(row_idx, col_idx)
                row_values.append(item.text() if item else "")
            cells.append(row_values)

        return {"columns": columns, "cells": cells}

    def add_grid_column(self):
        for table in (self.grid_compressions, self.grid_ecg, self.grid_meds):
            new_col = table.columnCount() + 1
            table.setColumnCount(new_col)
            table.setHorizontalHeaderItem(new_col - 1, QTableWidgetItem(str(new_col)))


class LocalStatusTab(QWidget):
    """Вкладка «Локальный статус»: диагноз + код МКБ + простой текст без
    подпунктов (в отличие от «Карты СМП», тут только одно текстовое поле)."""

    def __init__(self):
        super().__init__()

        self.current_case_id = None
        self.current_case_name = None
        self.current_mkb_code = None

        self.cases = []

        self.init_ui()
        self.load_cases()

    def init_ui(self):

        # ================= Колонка "Диагнозы" =================

        self.case_search = QLineEdit()
        self.case_search.setPlaceholderText("Поиск диагноза...")
        self.case_search.textChanged.connect(self.filter_cases)

        self.case_list = QListWidget()
        self.case_list.itemDoubleClicked.connect(self.open_case)

        self.open_case_button = QPushButton("Открыть")
        self.open_case_button.clicked.connect(self.open_case)

        self.delete_case_button = QPushButton("Удалить")
        self.delete_case_button.clicked.connect(self.delete_selected_case)

        case_actions_layout = QHBoxLayout()
        case_actions_layout.addWidget(self.open_case_button)
        case_actions_layout.addWidget(self.delete_case_button)

        self.add_case_button = QPushButton("+ Добавить диагноз")
        self.add_case_button.clicked.connect(self.add_case)

        case_layout = QVBoxLayout()
        case_layout.addWidget(QLabel("Диагнозы:"))
        case_layout.addWidget(self.case_search)
        case_layout.addWidget(self.case_list)
        case_layout.addLayout(case_actions_layout)
        case_layout.addWidget(self.add_case_button)

        # ================= Колонка "Текст" =================

        self.case_title = QLabel("Выберите диагноз")
        self.case_title.setStyleSheet("font-weight: bold; font-size: 16px;")

        self.text_edit = QTextEdit()

        self.save_button = QPushButton("Сохранить")
        self.save_button.clicked.connect(self.save_case)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.case_title)
        right_layout.addWidget(self.text_edit)
        right_layout.addWidget(self.save_button)

        # ================= Общая разметка =================

        content = QHBoxLayout()
        content.addLayout(case_layout, 1)
        content.addLayout(right_layout, 2)

        self.setLayout(content)

    def load_cases(self):
        db.create_tables()
        self.cases = db.get_local_status_cases()
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
            QMessageBox.warning(self, "03-Везём", "Выберите диагноз из списка.")
            return

        case_id = selected.data(Qt.UserRole)
        record = db.get_local_status_case(case_id)

        if record is None:
            return

        name, mkb_code, text = record

        self.current_case_id = case_id
        self.current_case_name = name
        self.current_mkb_code = mkb_code

        title = f"{name} — код по МКБ: {mkb_code}" if mkb_code else name
        self.case_title.setText(title)
        self.text_edit.setPlainText(text)

    def select_and_open_case(self, case_id):
        for i in range(self.case_list.count()):
            item = self.case_list.item(i)
            if item.data(Qt.UserRole) == case_id:
                self.case_list.setCurrentItem(item)
                break
        self.open_case()

    def add_case(self):

        name, ok = QInputDialog.getText(self, "Новый диагноз", "Название диагноза:")
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "03-Везём", "Введите название диагноза.")
            return

        mkb_code, ok = QInputDialog.getText(self, "Код по МКБ", "Код по МКБ (необязательно):")
        if not ok:
            mkb_code = ""
        mkb_code = mkb_code.strip()

        case_id = db.add_local_status_case(name, mkb_code, "")

        self.load_cases()
        self.case_search.setText("")
        self.select_and_open_case(case_id)

    def delete_selected_case(self):

        selected = self.case_list.currentItem()

        if not selected:
            QMessageBox.warning(self, "03-Везём", "Выберите диагноз для удаления.")
            return

        case_id = selected.data(Qt.UserRole)
        match = next((c for c in self.cases if c[0] == case_id), None)
        name = match[1] if match else ""

        confirm = QMessageBox.question(
            self, "Удаление диагноза",
            f"Удалить диагноз «{name}»?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if confirm != QMessageBox.Yes:
            return

        db.delete_local_status_case(case_id)

        if self.current_case_id == case_id:
            self.current_case_id = None
            self.current_case_name = None
            self.current_mkb_code = None
            self.case_title.setText("Выберите диагноз")
            self.text_edit.clear()

        self.load_cases()

    def save_case(self):

        if not self.current_case_id:
            QMessageBox.warning(self, "03-Везём", "Сначала откройте или добавьте диагноз.")
            return

        db.update_local_status_text(self.current_case_id, self.text_edit.toPlainText())
        QMessageBox.information(self, "03-Везём", "Сохранено.")


class CardFetchWorker(QThread):
    """Скачивает PDF карты вызова по номеру наряда в фоновом потоке,
    чтобы интерфейс не подвисал на время запроса к серверу."""

    finished_ok = Signal(str)   # путь к скачанному временному PDF-файлу
    finished_error = Signal(str)  # текст ошибки

    BASE_URL = "http://212.45.19.34:8081/ekvEmc/getCardPdf.ashx?a010={}"

    def __init__(self, naряд, parent=None):
        super().__init__(parent)
        self.naряд = naряд

    def run(self):
        url = self.BASE_URL.format(self.naряд)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "03-Vezem/1.0"})
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read()
        except urllib.error.HTTPError as e:
            self.finished_error.emit(f"Сервер ответил ошибкой {e.code}. Проверьте номер наряда.")
            return
        except urllib.error.URLError as e:
            self.finished_error.emit(f"Нет соединения с сервером карт ({e.reason}). Проверьте сеть/VPN.")
            return
        except Exception as e:
            self.finished_error.emit(f"Не удалось загрузить карту: {e}")
            return

        if not data or len(data) < 100:
            self.finished_error.emit("Сервер вернул пустой ответ — наряд с таким номером не найден.")
            return

        tmp_path = os.path.join(tempfile.gettempdir(), f"03vezem_card_{self.naряд}.pdf")
        try:
            with open(tmp_path, "wb") as f:
                f.write(data)
        except OSError as e:
            self.finished_error.emit(f"Не удалось сохранить временный файл: {e}")
            return

        self.finished_ok.emit(tmp_path)


class CardLookupTab(QWidget):
    """Вкладка «Подкрадули»: вводишь номер наряда — карта вызова
    открывается прямо здесь, без скачивания файла вручную (замена
    старого батника с dw.exe). Текст карты можно выделять/копировать
    из панели справа, либо скопировать весь целиком одной кнопкой."""

    def __init__(self):
        super().__init__()

        self.worker = None
        self.pdf_document = QPdfDocument(self)

        self.init_ui()

    def init_ui(self):

        self.naряд_input = QLineEdit()
        self.naряд_input.setPlaceholderText("Номер наряда (обычно 10 цифр)")
        self.naряд_input.returnPressed.connect(self.open_card)

        self.open_button = QPushButton("Открыть карту")
        self.open_button.clicked.connect(self.open_card)

        self.copy_text_button = QPushButton("Копировать текст")
        self.copy_text_button.clicked.connect(self.copy_all_text)
        self.copy_text_button.setEnabled(False)

        input_row = QHBoxLayout()
        input_row.addWidget(self.naряд_input)
        input_row.addWidget(self.open_button)
        input_row.addWidget(self.copy_text_button)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #777;")

        self.pdf_view = QPdfView()
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setPlaceholderText("Текст карты появится здесь после загрузки — можно выделять и копировать как обычный текст.")

        self.panes_splitter = QSplitter(Qt.Horizontal)
        self.panes_splitter.addWidget(self.pdf_view)
        self.panes_splitter.addWidget(self.text_view)
        self.panes_splitter.setStretchFactor(0, 3)
        self.panes_splitter.setStretchFactor(1, 2)
        self.panes_splitter.setChildrenCollapsible(False)

        layout = QVBoxLayout()
        layout.addLayout(input_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.panes_splitter)

        self.setLayout(layout)

    def open_card(self):

        raw = self.naряд_input.text().strip()
        naряд = re.sub(r"\D", "", raw)

        if not naряд:
            QMessageBox.warning(self, "03-Везём", "Введите номер наряда (только цифры).")
            return

        self.open_button.setEnabled(False)
        self.copy_text_button.setEnabled(False)
        self.text_view.clear()
        self.status_label.setText(f"Загрузка карты по наряду {naряд}...")

        self.worker = CardFetchWorker(naряд)
        self.worker.finished_ok.connect(self.on_fetch_ok)
        self.worker.finished_error.connect(self.on_fetch_error)
        self.worker.start()

    def on_fetch_ok(self, pdf_path):

        self.open_button.setEnabled(True)

        error = self.pdf_document.load(pdf_path)
        if error != QPdfDocument.Error.None_:
            self.status_label.setText("Сервер ответил, но файл не похож на карту вызова (PDF не читается).")
            return

        page_count = self.pdf_document.pageCount()

        pages_text = []
        for page in range(page_count):
            selection = self.pdf_document.getAllText(page)
            pages_text.append(selection.text() if selection.isValid() else "")
        full_text = "\n\n".join(pages_text).strip()

        self.text_view.setPlainText(full_text if full_text else "(на этой карте не найдено текста для копирования)")
        self.copy_text_button.setEnabled(bool(full_text))

        self.status_label.setText(f"Карта загружена — страниц: {page_count}")

    def on_fetch_error(self, message):
        self.open_button.setEnabled(True)
        self.status_label.setText(message)

    def copy_all_text(self):
        text = self.text_view.toPlainText()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.status_label.setText("Текст карты скопирован в буфер обмена.")


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("03-Везём")
        self.resize(1300, 700)

        tabs = QTabWidget()
        tabs.addTab(EmergencyCardTab(), "Карта СМП")
        tabs.addTab(ReanimationTab(), "Реанимация")
        tabs.addTab(LocalStatusTab(), "Локальный статус")
        tabs.addTab(CardLookupTab(), "Подкрадули")

        signature = QLabel("by Милосердов\nBild 2")
        signature.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        signature.setStyleSheet("color: #9a9a9a; font-size: 11px; padding: 4px 8px;")

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(tabs)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        footer_layout.addWidget(signature)
        central_layout.addLayout(footer_layout)

        self.setCentralWidget(central)


if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = MainWindow()

    window.show()

    sys.exit(app.exec())
