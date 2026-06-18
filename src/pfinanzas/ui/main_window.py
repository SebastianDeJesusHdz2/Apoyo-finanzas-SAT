from __future__ import annotations

import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsBlurEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QDoubleSpinBox,
)

from pfinanzas.core.db import ReceiptStore
from pfinanzas.core.models import DEFAULT_CATEGORIES, DOCUMENT_TYPES, ReceiptFilters, STATUSES
from pfinanzas.core.paths import CFDI_DIR, EXPORTS_DIR, RECEIPTS_DIR, resolve_storage_path, to_project_relative
from pfinanzas.services.cfdi import parse_cfdi_xml
from pfinanzas.services.ocr import analyze_image
from pfinanzas.services.reports import export_csv, export_pdf, export_xlsx


TABLE_COLUMNS = [
    ("id", "ID"),
    ("date", "Fecha"),
    ("category", "Categoria"),
    ("issuer_name", "Emisor"),
    ("issuer_rfc", "RFC"),
    ("description", "Descripcion"),
    ("subtotal", "Subtotal"),
    ("tax_iva", "IVA"),
    ("total", "Total"),
    ("uuid", "UUID"),
    ("status", "Estatus"),
]


class AcrylicBackdrop(QFrame):
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        base = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base.setColorAt(0.0, QColor(8, 11, 10, 188))
        base.setColorAt(0.48, QColor(15, 18, 17, 170))
        base.setColorAt(1.0, QColor(27, 25, 21, 160))
        painter.setBrush(base)
        painter.drawRoundedRect(rect, 8, 8)

        width = max(self.width(), 1)
        height = max(self.height(), 1)
        bands = [
            (QColor(31, 116, 92, 42), -9, -0.12, 0.20, 1.42, 92),
            (QColor(169, 118, 56, 34), -7, -0.08, 0.55, 1.34, 118),
            (QColor(78, 92, 86, 38), -6, 0.18, 0.82, 1.18, 86),
        ]
        for color, angle, x_factor, y_factor, w_factor, band_height in bands:
            painter.save()
            painter.translate(width * x_factor, height * y_factor)
            painter.rotate(angle)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(0, 0, width * w_factor, band_height), 22, 22)
            painter.restore()


class FinanceWindow(QMainWindow):
    def __init__(self, store: ReceiptStore) -> None:
        super().__init__()
        self.store = store
        self.current_id: int | None = None
        self.current_file_path = ""
        self.current_xml_path = ""
        self._loading_table = False

        self.setWindowTitle("PFinanzas")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self._apply_visual_style()
        self._build_ui()
        self._refresh_categories()
        self.new_receipt()
        self.load_records()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        root.setAttribute(Qt.WA_StyledBackground, True)
        root_layout = QGridLayout(root)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(0)

        backdrop = AcrylicBackdrop()
        backdrop.setObjectName("blurBackdrop")
        blur = QGraphicsBlurEffect(backdrop)
        blur.setBlurRadius(18)
        blur.setBlurHints(QGraphicsBlurEffect.QualityHint)
        backdrop.setGraphicsEffect(blur)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("mainSplitter")
        splitter.addWidget(self._build_form_panel())
        splitter.addWidget(self._build_table_panel())
        splitter.setSizes([430, 890])
        root_layout.addWidget(backdrop, 0, 0)
        root_layout.addWidget(splitter, 0, 0)
        backdrop.lower()
        splitter.raise_()
        self.setCentralWidget(root)
        self.statusBar().showMessage("Listo")

    def _build_form_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("glassPanel")
        panel.setAttribute(Qt.WA_StyledBackground, True)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(10, 10, 10, 10)

        title = QLabel("Registro")
        title.setObjectName("panelTitle")
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setObjectName("glassScroll")
        scroll.setWidgetResizable(True)
        form_host = QWidget()
        form_host.setObjectName("transparentHost")
        form = QFormLayout(form_host)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignRight)

        self.document_type = QComboBox()
        self.document_type.addItems(DOCUMENT_TYPES)
        self.status = QComboBox()
        self.status.addItems(STATUSES)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")

        self.category = QComboBox()
        self.category.setEditable(True)
        self.subcategory = QLineEdit()
        self.description = QLineEdit()
        self.issuer_name = QLineEdit()
        self.issuer_rfc = QLineEdit()
        self.receiver_name = QLineEdit()
        self.receiver_rfc = QLineEdit()
        self.uuid = QLineEdit()
        self.serie = QLineEdit()
        self.folio = QLineEdit()
        self.payment_form = QLineEdit()
        self.payment_method = QLineEdit()
        self.cfdi_use = QLineEdit()
        self.fiscal_regime = QLineEdit()
        self.currency = QLineEdit("MXN")

        self.subtotal = self._money_input()
        self.discount = self._money_input()
        self.tax_iva = self._money_input()
        self.tax_retained_iva = self._money_input()
        self.tax_retained_isr = self._money_input()
        self.total = self._money_input()

        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(90)
        self.raw_text = QPlainTextEdit()
        self.raw_text.setMaximumHeight(130)
        self.raw_text.setPlaceholderText("Texto OCR")

        self.file_label = QLabel("Sin imagen")
        self.file_label.setWordWrap(True)
        self.xml_label = QLabel("Sin XML")
        self.xml_label.setWordWrap(True)
        self.preview = QLabel()
        self.preview.setMinimumHeight(150)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFrameShape(QFrame.StyledPanel)
        self.preview.setText("Vista previa")

        form.addRow("Tipo", self.document_type)
        form.addRow("Estatus", self.status)
        form.addRow("Fecha", self.date_edit)
        form.addRow("Categoria", self.category)
        form.addRow("Subcategoria", self.subcategory)
        form.addRow("Descripcion", self.description)
        form.addRow("Emisor", self.issuer_name)
        form.addRow("RFC emisor", self.issuer_rfc)
        form.addRow("Receptor", self.receiver_name)
        form.addRow("RFC receptor", self.receiver_rfc)
        form.addRow("UUID", self.uuid)
        form.addRow("Serie", self.serie)
        form.addRow("Folio", self.folio)
        form.addRow("Forma pago", self.payment_form)
        form.addRow("Metodo pago", self.payment_method)
        form.addRow("Uso CFDI", self.cfdi_use)
        form.addRow("Regimen", self.fiscal_regime)
        form.addRow("Moneda", self.currency)
        form.addRow("Subtotal", self.subtotal)
        form.addRow("Descuento", self.discount)
        form.addRow("IVA", self.tax_iva)
        form.addRow("IVA retenido", self.tax_retained_iva)
        form.addRow("ISR retenido", self.tax_retained_isr)
        form.addRow("Total", self.total)
        form.addRow("Imagen", self.file_label)
        form.addRow("XML", self.xml_label)
        form.addRow("Notas", self.notes)
        form.addRow("OCR", self.raw_text)
        form.addRow("", self.preview)

        scroll.setWidget(form_host)
        outer.addWidget(scroll, stretch=1)

        import_row = QGridLayout()
        self.import_image_button = QPushButton("Importar imagen")
        self.import_image_button.clicked.connect(self.import_image)
        self.ocr_button = QPushButton("Analizar OCR")
        self.ocr_button.clicked.connect(self.run_ocr)
        self.import_xml_button = QPushButton("Importar XML CFDI")
        self.import_xml_button.clicked.connect(self.import_xml)
        import_row.addWidget(self.import_image_button, 0, 0)
        import_row.addWidget(self.ocr_button, 0, 1)
        import_row.addWidget(self.import_xml_button, 1, 0, 1, 2)
        outer.addLayout(import_row)

        action_row = QHBoxLayout()
        self.new_button = QPushButton("Nuevo")
        self.new_button.clicked.connect(self.new_receipt)
        self.save_button = QPushButton("Guardar")
        self.save_button.clicked.connect(self.save_receipt)
        self.delete_button = QPushButton("Eliminar")
        self.delete_button.clicked.connect(self.delete_receipt)
        action_row.addWidget(self.new_button)
        action_row.addWidget(self.save_button)
        action_row.addWidget(self.delete_button)
        outer.addLayout(action_row)

        return panel

    def _build_table_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("glassPanel")
        panel.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)

        header_row = QHBoxLayout()
        title = QLabel("Recibos y CFDI")
        title.setObjectName("panelTitle")
        header_row.addWidget(title)
        header_row.addStretch()
        self.export_csv_button = QPushButton("CSV")
        self.export_csv_button.clicked.connect(lambda: self.export_report("csv"))
        self.export_xlsx_button = QPushButton("Excel")
        self.export_xlsx_button.clicked.connect(lambda: self.export_report("xlsx"))
        self.export_pdf_button = QPushButton("PDF")
        self.export_pdf_button.clicked.connect(lambda: self.export_report("pdf"))
        header_row.addWidget(self.export_csv_button)
        header_row.addWidget(self.export_xlsx_button)
        header_row.addWidget(self.export_pdf_button)
        layout.addLayout(header_row)

        filters = QGroupBox("Filtros")
        filters.setObjectName("filterBox")
        filters_layout = QGridLayout(filters)
        self.period = QComboBox()
        self.period.addItems(["Todo", "Semana actual", "Este mes", "Mes anterior", "Este año", "Rango manual"])
        self.period.currentTextChanged.connect(self.apply_period)
        self.filter_from = QDateEdit()
        self.filter_from.setCalendarPopup(True)
        self.filter_from.setDisplayFormat("yyyy-MM-dd")
        self.filter_to = QDateEdit()
        self.filter_to.setCalendarPopup(True)
        self.filter_to.setDisplayFormat("yyyy-MM-dd")
        self.filter_category = QComboBox()
        self.filter_status = QComboBox()
        self.filter_status.addItems(["Todos", *STATUSES])
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar emisor, RFC, UUID, descripcion")

        self.apply_filter_button = QPushButton("Aplicar")
        self.apply_filter_button.clicked.connect(self.load_records)
        self.clear_filter_button = QToolButton()
        self.clear_filter_button.setText("Limpiar")
        self.clear_filter_button.clicked.connect(self.clear_filters)

        filters_layout.addWidget(QLabel("Periodo"), 0, 0)
        filters_layout.addWidget(self.period, 0, 1)
        filters_layout.addWidget(QLabel("Desde"), 0, 2)
        filters_layout.addWidget(self.filter_from, 0, 3)
        filters_layout.addWidget(QLabel("Hasta"), 0, 4)
        filters_layout.addWidget(self.filter_to, 0, 5)
        filters_layout.addWidget(QLabel("Categoria"), 1, 0)
        filters_layout.addWidget(self.filter_category, 1, 1)
        filters_layout.addWidget(QLabel("Estatus"), 1, 2)
        filters_layout.addWidget(self.filter_status, 1, 3)
        filters_layout.addWidget(self.search, 1, 4)
        filters_layout.addWidget(self.apply_filter_button, 1, 5)
        filters_layout.addWidget(self.clear_filter_button, 1, 6)
        layout.addWidget(filters)

        summary = QHBoxLayout()
        self.count_label = QLabel("Registros: 0")
        self.subtotal_label = QLabel("Subtotal: $0.00")
        self.iva_label = QLabel("IVA: $0.00")
        self.total_label = QLabel("Total: $0.00")
        for label in (self.count_label, self.subtotal_label, self.iva_label, self.total_label):
            label.setObjectName("summaryLabel")
            summary.addWidget(label)
        summary.addStretch()
        layout.addLayout(summary)

        self.table = QTableWidget(0, len(TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels([label for _, label in TABLE_COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self.table_selection_changed)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.hideColumn(0)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, stretch=1)

        self.apply_period("Todo")
        return panel

    def _apply_visual_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: transparent;
            }
            #appRoot {
                background-color: rgba(4, 6, 6, 92);
                border: 1px solid rgba(255, 255, 255, 38);
                border-radius: 8px;
            }
            #blurBackdrop {
                background: transparent;
                border-radius: 8px;
            }
            #mainSplitter {
                background: transparent;
            }
            #glassPanel {
                background-color: rgba(13, 16, 15, 194);
                border: 1px solid rgba(255, 255, 255, 42);
                border-radius: 8px;
            }
            #glassScroll,
            #glassScroll > QWidget,
            #transparentHost {
                background: transparent;
                border: none;
            }
            #panelTitle {
                color: #ecf2ef;
                font-size: 18px;
                font-weight: 700;
                padding: 2px 0 8px 0;
            }
            QLabel {
                color: #d5dfdb;
            }
            #summaryLabel {
                background-color: rgba(22, 27, 26, 176);
                border: 1px solid rgba(94, 111, 105, 130);
                border-radius: 6px;
                padding: 6px 10px;
                color: #edf4f1;
                font-weight: 600;
            }
            QGroupBox#filterBox {
                background-color: rgba(17, 21, 20, 166);
                border: 1px solid rgba(94, 111, 105, 130);
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px 10px 10px 10px;
                color: #e7efeb;
                font-weight: 600;
            }
            QGroupBox#filterBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 4px;
            }
            QLineEdit,
            QPlainTextEdit,
            QComboBox,
            QDateEdit,
            QDoubleSpinBox {
                background-color: rgba(9, 12, 12, 212);
                border: 1px solid rgba(92, 111, 104, 170);
                border-radius: 6px;
                color: #eef4f1;
                padding: 5px 7px;
                selection-background-color: rgba(42, 132, 108, 205);
                selection-color: white;
            }
            QLineEdit:focus,
            QPlainTextEdit:focus,
            QComboBox:focus,
            QDateEdit:focus,
            QDoubleSpinBox:focus {
                border: 1px solid rgba(80, 177, 146, 220);
                background-color: rgba(13, 18, 17, 232);
            }
            QComboBox QAbstractItemView {
                background-color: rgba(10, 13, 13, 242);
                border: 1px solid rgba(92, 111, 104, 190);
                color: #eef4f1;
                selection-background-color: rgba(42, 132, 108, 210);
                selection-color: #ffffff;
            }
            QComboBox::drop-down,
            QDateEdit::drop-down,
            QDoubleSpinBox::up-button,
            QDoubleSpinBox::down-button {
                background-color: rgba(18, 24, 22, 160);
                border-left: 1px solid rgba(92, 111, 104, 120);
                width: 22px;
            }
            QComboBox::down-arrow,
            QDateEdit::down-arrow {
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #d5dfdb;
                margin-right: 7px;
            }
            QPushButton,
            QToolButton {
                background-color: rgba(24, 50, 44, 220);
                border: 1px solid rgba(110, 144, 134, 92);
                border-radius: 6px;
                color: #f0f6f3;
                padding: 7px 11px;
                font-weight: 600;
            }
            QPushButton:hover,
            QToolButton:hover {
                background-color: rgba(35, 77, 66, 232);
            }
            QPushButton:pressed,
            QToolButton:pressed {
                background-color: rgba(12, 31, 27, 240);
            }
            QTableWidget {
                background-color: rgba(8, 10, 10, 178);
                alternate-background-color: rgba(18, 22, 21, 178);
                border: 1px solid rgba(94, 111, 105, 130);
                border-radius: 8px;
                color: #e7efeb;
                gridline-color: rgba(82, 96, 91, 120);
                selection-background-color: rgba(40, 128, 104, 205);
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: rgba(21, 26, 25, 225);
                border: none;
                border-right: 1px solid rgba(82, 96, 91, 130);
                border-bottom: 1px solid rgba(94, 111, 105, 150);
                color: #eaf1ee;
                padding: 6px;
                font-weight: 700;
            }
            QSplitter::handle {
                background-color: rgba(255, 255, 255, 30);
                margin: 8px 4px;
                border-radius: 3px;
            }
            QStatusBar {
                background-color: rgba(8, 11, 10, 178);
                color: #d5dfdb;
                border-top: 1px solid rgba(94, 111, 105, 120);
            }
            QScrollBar:vertical,
            QScrollBar:horizontal {
                background-color: rgba(7, 9, 9, 140);
                border: none;
                margin: 0;
                width: 12px;
                height: 12px;
            }
            QScrollBar::handle:vertical,
            QScrollBar::handle:horizontal {
                background-color: rgba(82, 104, 97, 190);
                border-radius: 5px;
                min-height: 28px;
                min-width: 28px;
            }
            QScrollBar::handle:vertical:hover,
            QScrollBar::handle:horizontal:hover {
                background-color: rgba(107, 139, 129, 220);
            }
            QScrollBar::add-line,
            QScrollBar::sub-line,
            QScrollBar::add-page,
            QScrollBar::sub-page {
                background: transparent;
                border: none;
            }
            QLabel[frameShape="6"] {
                background-color: rgba(12, 15, 15, 150);
                border: 1px solid rgba(94, 111, 105, 130);
                border-radius: 8px;
            }
            """
        )

    def _money_input(self) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setDecimals(2)
        widget.setMaximum(999_999_999.99)
        widget.setPrefix("$")
        widget.setGroupSeparatorShown(True)
        return widget

    def _refresh_categories(self) -> None:
        categories = self.store.list_categories() or DEFAULT_CATEGORIES
        current = self.category.currentText() if hasattr(self, "category") else ""
        filter_current = self.filter_category.currentText() if hasattr(self, "filter_category") else ""

        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItems(categories)
        if current:
            self.category.setCurrentText(current)
        self.category.blockSignals(False)

        self.filter_category.blockSignals(True)
        self.filter_category.clear()
        self.filter_category.addItems(["Todas", *categories])
        if filter_current:
            self.filter_category.setCurrentText(filter_current)
        self.filter_category.blockSignals(False)

    def apply_period(self, period: str) -> None:
        today = date.today()
        date_from: date | None
        date_to: date | None

        if period == "Semana actual":
            date_from = today - timedelta(days=today.weekday())
            date_to = date_from + timedelta(days=6)
        elif period == "Este mes":
            date_from = today.replace(day=1)
            next_month = (date_from.replace(day=28) + timedelta(days=4)).replace(day=1)
            date_to = next_month - timedelta(days=1)
        elif period == "Mes anterior":
            first_this_month = today.replace(day=1)
            date_to = first_this_month - timedelta(days=1)
            date_from = date_to.replace(day=1)
        elif period == "Este año":
            date_from = today.replace(month=1, day=1)
            date_to = today.replace(month=12, day=31)
        elif period == "Rango manual":
            return
        else:
            date_from = None
            date_to = None

        if date_from and date_to:
            self.filter_from.setDate(_to_qdate(date_from))
            self.filter_to.setDate(_to_qdate(date_to))
        else:
            self.filter_from.setDate(_to_qdate(today.replace(month=1, day=1)))
            self.filter_to.setDate(_to_qdate(today))
        self.load_records()

    def current_filters(self) -> ReceiptFilters:
        period = self.period.currentText()
        date_from = _from_qdate(self.filter_from.date()) if period != "Todo" else None
        date_to = _from_qdate(self.filter_to.date()) if period != "Todo" else None
        return ReceiptFilters(
            date_from=date_from,
            date_to=date_to,
            category=self.filter_category.currentText(),
            status=self.filter_status.currentText(),
            text=self.search.text().strip() or None,
        )

    def clear_filters(self) -> None:
        self.period.setCurrentText("Todo")
        self.filter_category.setCurrentText("Todas")
        self.filter_status.setCurrentText("Todos")
        self.search.clear()
        self.apply_period("Todo")

    def load_records(self) -> None:
        filters = self.current_filters()
        records = self.store.list(filters)
        totals = self.store.totals(filters)

        self._loading_table = True
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for record in records:
            row_index = self.table.rowCount()
            self.table.insertRow(row_index)
            for column_index, (key, _) in enumerate(TABLE_COLUMNS):
                value = record.get(key)
                if key in {"subtotal", "tax_iva", "total"}:
                    text = _money(value)
                else:
                    text = str(value or "")
                item = QTableWidgetItem(text)
                if key == "id":
                    item.setData(Qt.UserRole, int(record["id"]))
                if key in {"subtotal", "tax_iva", "total"}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_index, column_index, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.table.hideColumn(0)
        self._loading_table = False

        self.count_label.setText(f"Registros: {int(totals.get('count') or 0)}")
        self.subtotal_label.setText(f"Subtotal: {_money(totals.get('subtotal'))}")
        self.iva_label.setText(f"IVA: {_money(totals.get('tax_iva'))}")
        self.total_label.setText(f"Total: {_money(totals.get('total'))}")
        self.statusBar().showMessage(f"{len(records)} registros cargados")

    def table_selection_changed(self) -> None:
        if self._loading_table or not self.table.selectedItems():
            return
        selected_row = self.table.currentRow()
        id_item = self.table.item(selected_row, 0)
        if id_item is None:
            return
        receipt_id = id_item.data(Qt.UserRole)
        record = self.store.get(int(receipt_id))
        if record:
            self.load_form(record)

    def new_receipt(self) -> None:
        self.current_id = None
        self.current_file_path = ""
        self.current_xml_path = ""
        self.document_type.setCurrentText("Recibo")
        self.status.setCurrentText("por revisar")
        self.date_edit.setDate(QDate.currentDate())
        self.category.setCurrentText("Sin categoria")
        for field in (
            self.subcategory,
            self.description,
            self.issuer_name,
            self.issuer_rfc,
            self.receiver_name,
            self.receiver_rfc,
            self.uuid,
            self.serie,
            self.folio,
            self.payment_form,
            self.payment_method,
            self.cfdi_use,
            self.fiscal_regime,
        ):
            field.clear()
        self.currency.setText("MXN")
        for field in (
            self.subtotal,
            self.discount,
            self.tax_iva,
            self.tax_retained_iva,
            self.tax_retained_isr,
            self.total,
        ):
            field.setValue(0)
        self.notes.clear()
        self.raw_text.clear()
        self.file_label.setText("Sin imagen")
        self.xml_label.setText("Sin XML")
        self.preview.setPixmap(QPixmap())
        self.preview.setText("Vista previa")
        self.table.clearSelection()
        self.statusBar().showMessage("Nuevo registro")

    def load_form(self, record: dict) -> None:
        self.current_id = int(record["id"])
        self.current_file_path = record.get("file_path") or ""
        self.current_xml_path = record.get("xml_path") or ""

        self.document_type.setCurrentText(record.get("document_type") or "Recibo")
        self.status.setCurrentText(record.get("status") or "por revisar")
        self.date_edit.setDate(_to_qdate(_parse_date(record.get("date")) or date.today()))
        self.category.setCurrentText(record.get("category") or "Sin categoria")
        self.subcategory.setText(record.get("subcategory") or "")
        self.description.setText(record.get("description") or "")
        self.issuer_name.setText(record.get("issuer_name") or "")
        self.issuer_rfc.setText(record.get("issuer_rfc") or "")
        self.receiver_name.setText(record.get("receiver_name") or "")
        self.receiver_rfc.setText(record.get("receiver_rfc") or "")
        self.uuid.setText(record.get("uuid") or "")
        self.serie.setText(record.get("serie") or "")
        self.folio.setText(record.get("folio") or "")
        self.payment_form.setText(record.get("payment_form") or "")
        self.payment_method.setText(record.get("payment_method") or "")
        self.cfdi_use.setText(record.get("cfdi_use") or "")
        self.fiscal_regime.setText(record.get("fiscal_regime") or "")
        self.currency.setText(record.get("currency") or "MXN")
        self.subtotal.setValue(float(record.get("subtotal") or 0))
        self.discount.setValue(float(record.get("discount") or 0))
        self.tax_iva.setValue(float(record.get("tax_iva") or 0))
        self.tax_retained_iva.setValue(float(record.get("tax_retained_iva") or 0))
        self.tax_retained_isr.setValue(float(record.get("tax_retained_isr") or 0))
        self.total.setValue(float(record.get("total") or 0))
        self.notes.setPlainText(record.get("notes") or "")
        self.raw_text.setPlainText(record.get("raw_text") or "")
        self.file_label.setText(self.current_file_path or "Sin imagen")
        self.xml_label.setText(self.current_xml_path or "Sin XML")
        self._load_preview(self.current_file_path)
        self.statusBar().showMessage(f"Registro {self.current_id} cargado")

    def form_values(self) -> dict[str, object]:
        return {
            "id": self.current_id,
            "document_type": self.document_type.currentText(),
            "status": self.status.currentText(),
            "issuer_name": self.issuer_name.text().strip(),
            "issuer_rfc": self.issuer_rfc.text().strip().upper(),
            "receiver_name": self.receiver_name.text().strip(),
            "receiver_rfc": self.receiver_rfc.text().strip().upper(),
            "date": _from_qdate(self.date_edit.date()).isoformat(),
            "category": self.category.currentText().strip() or "Sin categoria",
            "subcategory": self.subcategory.text().strip(),
            "description": self.description.text().strip(),
            "payment_method": self.payment_method.text().strip(),
            "payment_form": self.payment_form.text().strip(),
            "cfdi_use": self.cfdi_use.text().strip(),
            "fiscal_regime": self.fiscal_regime.text().strip(),
            "currency": self.currency.text().strip().upper() or "MXN",
            "subtotal": self.subtotal.value(),
            "discount": self.discount.value(),
            "tax_iva": self.tax_iva.value(),
            "tax_retained_iva": self.tax_retained_iva.value(),
            "tax_retained_isr": self.tax_retained_isr.value(),
            "total": self.total.value(),
            "uuid": self.uuid.text().strip().upper(),
            "serie": self.serie.text().strip(),
            "folio": self.folio.text().strip(),
            "file_path": self.current_file_path,
            "xml_path": self.current_xml_path,
            "notes": self.notes.toPlainText().strip(),
            "raw_text": self.raw_text.toPlainText().strip(),
        }

    def save_receipt(self) -> None:
        values = self.form_values()
        saved_id = self.store.save(values)
        self.current_id = saved_id
        self._refresh_categories()
        self.load_records()
        self.statusBar().showMessage(f"Registro {saved_id} guardado")

    def delete_receipt(self) -> None:
        if not self.current_id:
            return
        response = QMessageBox.question(
            self,
            "Eliminar registro",
            "Eliminar este registro de la base de datos? Los archivos importados no se borran.",
        )
        if response != QMessageBox.Yes:
            return
        self.store.delete(self.current_id)
        self.new_receipt()
        self.load_records()
        self.statusBar().showMessage("Registro eliminado")

    def import_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar recibo",
            str(Path.home()),
            "Imagenes (*.png *.jpg *.jpeg *.webp *.tif *.tiff *.bmp);;Todos (*.*)",
        )
        if not filename:
            return
        target = _copy_into_storage(Path(filename), RECEIPTS_DIR)
        self.current_file_path = to_project_relative(target)
        self.file_label.setText(self.current_file_path)
        self._load_preview(self.current_file_path)
        self.statusBar().showMessage("Imagen importada")

    def run_ocr(self) -> None:
        image_path = resolve_storage_path(self.current_file_path)
        if image_path is None or not image_path.exists():
            QMessageBox.information(self, "OCR", "Primero importa una imagen de recibo.")
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            _, parsed = analyze_image(image_path)
        except Exception as exc:
            QMessageBox.warning(self, "OCR no disponible", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.apply_parsed_data(parsed, only_empty=True)
        self.statusBar().showMessage("OCR aplicado; revisa los campos antes de guardar")

    def import_xml(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar XML CFDI",
            str(Path.home()),
            "XML CFDI (*.xml);;Todos (*.*)",
        )
        if not filename:
            return
        source = Path(filename)
        try:
            parsed = parse_cfdi_xml(source)
        except Exception as exc:
            QMessageBox.warning(self, "XML CFDI", f"No pude leer el XML:\n{exc}")
            return

        target = _copy_into_storage(source, CFDI_DIR)
        self.current_xml_path = to_project_relative(target)
        parsed["xml_path"] = self.current_xml_path
        self.apply_parsed_data(parsed, only_empty=False)
        self.xml_label.setText(self.current_xml_path)
        self.statusBar().showMessage("XML CFDI importado")

    def apply_parsed_data(self, parsed: dict[str, object], only_empty: bool) -> None:
        setters = {
            "document_type": lambda value: self.document_type.setCurrentText(str(value)),
            "status": lambda value: self.status.setCurrentText(str(value)),
            "issuer_name": self.issuer_name.setText,
            "issuer_rfc": lambda value: self.issuer_rfc.setText(str(value).upper()),
            "receiver_name": self.receiver_name.setText,
            "receiver_rfc": lambda value: self.receiver_rfc.setText(str(value).upper()),
            "category": lambda value: self.category.setCurrentText(str(value)),
            "subcategory": self.subcategory.setText,
            "description": self.description.setText,
            "payment_method": self.payment_method.setText,
            "payment_form": self.payment_form.setText,
            "cfdi_use": self.cfdi_use.setText,
            "fiscal_regime": self.fiscal_regime.setText,
            "currency": lambda value: self.currency.setText(str(value).upper()),
            "uuid": lambda value: self.uuid.setText(str(value).upper()),
            "serie": self.serie.setText,
            "folio": self.folio.setText,
            "notes": lambda value: self.notes.setPlainText(str(value)),
            "raw_text": lambda value: self.raw_text.setPlainText(str(value)),
        }
        line_edit_getters = {
            "issuer_name": self.issuer_name.text,
            "issuer_rfc": self.issuer_rfc.text,
            "receiver_name": self.receiver_name.text,
            "receiver_rfc": self.receiver_rfc.text,
            "subcategory": self.subcategory.text,
            "description": self.description.text,
            "payment_method": self.payment_method.text,
            "payment_form": self.payment_form.text,
            "cfdi_use": self.cfdi_use.text,
            "fiscal_regime": self.fiscal_regime.text,
            "currency": self.currency.text,
            "uuid": self.uuid.text,
            "serie": self.serie.text,
            "folio": self.folio.text,
        }
        amount_fields = {
            "subtotal": self.subtotal,
            "discount": self.discount,
            "tax_iva": self.tax_iva,
            "tax_retained_iva": self.tax_retained_iva,
            "tax_retained_isr": self.tax_retained_isr,
            "total": self.total,
        }

        if parsed.get("date"):
            parsed_date = _parse_date(str(parsed["date"]))
            if parsed_date:
                self.date_edit.setDate(_to_qdate(parsed_date))

        for key, setter in setters.items():
            value = parsed.get(key)
            if value in (None, ""):
                continue
            if only_empty and key in line_edit_getters and line_edit_getters[key]().strip():
                continue
            setter(str(value))

        for key, widget in amount_fields.items():
            value = parsed.get(key)
            if value in (None, ""):
                continue
            if only_empty and widget.value() != 0:
                continue
            try:
                widget.setValue(float(value))
            except (TypeError, ValueError):
                continue

        if parsed.get("xml_path"):
            self.current_xml_path = str(parsed["xml_path"])
            self.xml_label.setText(self.current_xml_path)

    def export_report(self, kind: str) -> None:
        records = self.store.list(self.current_filters())
        if not records:
            QMessageBox.information(self, "Reporte", "No hay registros para exportar con los filtros actuales.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        default_name = EXPORTS_DIR / f"pfinanzas_{timestamp}.{kind}"
        filters = {
            "csv": "CSV (*.csv)",
            "xlsx": "Excel (*.xlsx)",
            "pdf": "PDF (*.pdf)",
        }
        filename, _ = QFileDialog.getSaveFileName(self, "Guardar reporte", str(default_name), filters[kind])
        if not filename:
            return

        try:
            if kind == "csv":
                output = export_csv(records, filename)
            elif kind == "xlsx":
                output = export_xlsx(records, filename)
            else:
                output = export_pdf(records, filename)
        except Exception as exc:
            QMessageBox.warning(self, "Reporte", f"No pude generar el reporte:\n{exc}")
            return
        self.statusBar().showMessage(f"Reporte generado: {output}")

    def _load_preview(self, value: str) -> None:
        path = resolve_storage_path(value)
        if path is None or not path.exists():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("Vista previa")
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("No hay vista previa")
            return
        self.preview.setText("")
        self.preview.setPixmap(pixmap.scaled(360, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation))


def _copy_into_storage(source: Path, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(char if char.isalnum() or char in ".-_" else "_" for char in source.name)
    target = directory / f"{stamp}_{safe_name}"
    counter = 1
    while target.exists():
        target = directory / f"{stamp}_{counter}_{safe_name}"
        counter += 1
    shutil.copy2(source, target)
    return target


def _to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def _from_qdate(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


def _parse_date(value: object) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _money(value: object) -> str:
    try:
        return f"${float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"
