"""
Mass Lookup Tool - Main GUI Window v5
======================================

Simplified batch-first design:
- Mass mode: batch masses, multi-adduct, configurable result limit
- Formula mode: batch formulas, configurable result limit
- Both modes support single or multiple queries

Usage:
    python main.py
"""

import sys
import csv
import re
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QMessageBox, QHeaderView, QRadioButton, QButtonGroup,
    QComboBox, QFileDialog, QCheckBox, QAbstractItemView, QTextEdit,
    QSpinBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from search.search_engine import SearchEngine


# ─────────────────────────────────────────────
#  ADDUCT DEFINITIONS
# ─────────────────────────────────────────────

ADDUCTS = {
    "Neutral (exact mass)"    : (0.0,        "neutral"),
    "[M+H]⁺  (+1.00728)"     : (1.007276,   "positive"),
    "[M+Na]⁺ (+22.98922)"    : (22.989218,  "positive"),
    "[M+K]⁺  (+38.96316)"    : (38.963158,  "positive"),
    "[M+NH4]⁺ (+18.03437)"   : (18.034374,  "positive"),
    "[M-H]⁻  (-1.00728)"     : (-1.007276,  "negative"),
    "[M+Cl]⁻ (+34.96940)"    : (34.969402,  "negative"),
    "[M+FA-H]⁻ (+44.99820)"  : (44.998201,  "negative"),
}

SOURCE_URLS = {
    "HMDB"     : "https://hmdb.ca/metabolites/{id}",
    "ChEBI"    : "https://www.ebi.ac.uk/chebi/searchId.do?chebiId={id}",
    "LipidMaps": "https://www.lipidmaps.org/databases/lmsd/{id}",
}

SOURCE_COLORS = {
    "HMDB"     : QColor(220, 240, 255),
    "ChEBI"    : QColor(220, 255, 220),
    "LipidMaps": QColor(255, 240, 220),
}


class MassLookupWindow(QMainWindow):
    """Main application window — v5 simplified batch."""

    def __init__(self):
        super().__init__()

        try:
            self.search_engine = SearchEngine()
            self.stats         = self.search_engine.get_stats()
            self.db_loaded     = True
        except FileNotFoundError as e:
            self.db_loaded = False
            self.stats     = {}
            QMessageBox.critical(self, "Database Error", str(e))

        self.last_results       = []
        self.last_search_params = {}

        self.init_ui()

        if self.db_loaded:
            parts = [f"{src}: {cnt:,}" for src, cnt in self.stats["by_source"].items()]
            self.update_status("Database loaded — " + " | ".join(parts))

    def init_ui(self):
        self.setWindowTitle("LC-MS Mass Lookup Tool v5 — Batch Search")
        self.setGeometry(100, 100, 1400, 850)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout()
        central.setLayout(layout)

        layout.addWidget(self.create_search_panel())
        layout.addWidget(self.create_db_filter_panel())
        layout.addWidget(self.create_results_panel())
        layout.addWidget(self.create_status_bar())

    def create_search_panel(self):
        group  = QGroupBox("Search Parameters")
        layout = QVBoxLayout()

        # ── Search mode row ──────────────────
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Search Mode:"))

        self.mode_group         = QButtonGroup()
        self.mass_mode_radio    = QRadioButton("Mass")
        self.formula_mode_radio = QRadioButton("Formula")

        self.mass_mode_radio.setChecked(True)

        self.mode_group.addButton(self.mass_mode_radio)
        self.mode_group.addButton(self.formula_mode_radio)

        self.mass_mode_radio.toggled.connect(self.on_mode_changed)

        mode_row.addWidget(self.mass_mode_radio)
        mode_row.addWidget(self.formula_mode_radio)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # ── Mass input ───────────────────────
        self.mass_label = QLabel("Observed Masses (one per line or comma-separated):")
        layout.addWidget(self.mass_label)

        self.mass_input = QTextEdit()
        self.mass_input.setPlaceholderText("Examples:\n181.071\n194.079\n342.116\n\nOr: 181.071, 194.079, 342.116")
        self.mass_input.setMaximumHeight(100)
        layout.addWidget(self.mass_input)

        mass_params_row = QHBoxLayout()

        self.tol_label = QLabel("Tolerance (±):")
        mass_params_row.addWidget(self.tol_label)

        self.tolerance_input = QLineEdit()
        self.tolerance_input.setText("0.5")
        self.tolerance_input.setMaximumWidth(80)
        mass_params_row.addWidget(self.tolerance_input)

        self.tol_unit_label = QLabel("Da")
        mass_params_row.addWidget(self.tol_unit_label)

        self.mass_top_n_label = QLabel("Max results per query:")
        mass_params_row.addWidget(self.mass_top_n_label)

        self.mass_top_n_spin = QSpinBox()
        self.mass_top_n_spin.setMinimum(1)
        self.mass_top_n_spin.setMaximum(500)
        self.mass_top_n_spin.setValue(20)
        self.mass_top_n_spin.setMaximumWidth(80)
        mass_params_row.addWidget(self.mass_top_n_spin)

        mass_params_row.addStretch()
        layout.addLayout(mass_params_row)

        # ── Formula input ────────────────────
        self.formula_label = QLabel("Molecular Formulas (one per line or comma-separated):")
        self.formula_label.hide()
        layout.addWidget(self.formula_label)

        self.formula_input = QTextEdit()
        self.formula_input.setPlaceholderText("Examples:\nC6H12O6\nC12H22O11\nC5H10O5\n\nOr: C6H12O6, C12H22O11")
        self.formula_input.setMaximumHeight(100)
        self.formula_input.hide()
        layout.addWidget(self.formula_input)

        formula_params_row = QHBoxLayout()

        self.formula_top_n_label = QLabel("Max results per formula:")
        self.formula_top_n_label.hide()
        formula_params_row.addWidget(self.formula_top_n_label)

        self.formula_top_n_spin = QSpinBox()
        self.formula_top_n_spin.setMinimum(1)
        self.formula_top_n_spin.setMaximum(500)
        self.formula_top_n_spin.setValue(100)
        self.formula_top_n_spin.setMaximumWidth(80)
        self.formula_top_n_spin.hide()
        formula_params_row.addWidget(self.formula_top_n_spin)

        formula_params_row.addStretch()
        layout.addLayout(formula_params_row)

        # ── Adduct selection ─────────────────
        self.adduct_group = QGroupBox("Adducts to Search (select one or more)")
        adduct_layout = QVBoxLayout()

        self.adduct_checkboxes = {}

        col1_layout = QVBoxLayout()
        col2_layout = QVBoxLayout()

        adduct_keys = list(ADDUCTS.keys())
        mid = len(adduct_keys) // 2

        for i, label in enumerate(adduct_keys):
            cb = QCheckBox(label)
            if label == "[M+H]⁺  (+1.00728)":
                cb.setChecked(True)
            self.adduct_checkboxes[label] = cb

            if i < mid:
                col1_layout.addWidget(cb)
            else:
                col2_layout.addWidget(cb)

        cols_layout = QHBoxLayout()
        cols_layout.addLayout(col1_layout)
        cols_layout.addLayout(col2_layout)
        cols_layout.addStretch()

        adduct_layout.addLayout(cols_layout)
        self.adduct_group.setLayout(adduct_layout)
        layout.addWidget(self.adduct_group)

        # ── Button row ───────────────────────
        btn_row = QHBoxLayout()

        self.search_button = QPushButton("Search")
        self.search_button.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "padding: 10px 24px; font-weight: bold; font-size: 14px; }"
        )
        self.search_button.clicked.connect(self.perform_search)
        btn_row.addWidget(self.search_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_search)
        btn_row.addWidget(self.clear_button)

        self.copy_button = QPushButton("Copy Selected Row")
        self.copy_button.clicked.connect(self.copy_selected_row)
        self.copy_button.setEnabled(False)
        btn_row.addWidget(self.copy_button)

        self.export_button = QPushButton("Export to CSV")
        self.export_button.clicked.connect(self.export_to_csv)
        self.export_button.setEnabled(False)
        btn_row.addWidget(self.export_button)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        group.setLayout(layout)
        return group

    def create_db_filter_panel(self):
        group  = QGroupBox("Database Filter")
        layout = QHBoxLayout()

        self.db_checkboxes = {}
        sources = list(self.stats.get("by_source", {}).keys()) or ["HMDB", "ChEBI", "LipidMaps"]

        for source in sources:
            count = self.stats.get("by_source", {}).get(source, 0)
            cb    = QCheckBox(f"{source}  ({count:,})")
            cb.setChecked(True)
            self.db_checkboxes[source] = cb
            layout.addWidget(cb)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def create_results_panel(self):
        group  = QGroupBox("Results")
        layout = QVBoxLayout()

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels([
            "Name", "Formula", "Exact Mass (Da)",
            "Error (Da)", "Error (ppm)", "Adduct", "Source", "Source URL"
        ])

        self.results_table.setAlternatingRowColors(False)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.results_table.itemSelectionChanged.connect(self.on_selection_changed)

        hdr = self.results_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)            # Name
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Formula
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Mass
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Error Da
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Error ppm
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Adduct
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Source
        hdr.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # URL

        layout.addWidget(self.results_table)
        group.setLayout(layout)
        return group

    def create_status_bar(self):
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("QLabel { padding: 5px; }")
        return self.status_label

    def on_mode_changed(self):
        is_mass = self.mass_mode_radio.isChecked()

        # Mass widgets
        for w in [self.mass_label, self.mass_input, self.tol_label,
                  self.tolerance_input, self.tol_unit_label,
                  self.mass_top_n_label, self.mass_top_n_spin, self.adduct_group]:
            w.setVisible(is_mass)

        # Formula widgets
        for w in [self.formula_label, self.formula_input,
                  self.formula_top_n_label, self.formula_top_n_spin]:
            w.setVisible(not is_mass)

        (self.mass_input if is_mass else self.formula_input).setFocus()

    def get_selected_sources(self):
        selected = [src for src, cb in self.db_checkboxes.items() if cb.isChecked()]
        return selected if selected else None

    def get_selected_adducts(self):
        selected = []
        for label, cb in self.adduct_checkboxes.items():
            if cb.isChecked():
                mass_delta, _ = ADDUCTS[label]
                selected.append((label, mass_delta))
        return selected

    def perform_search(self):
        if not self.db_loaded:
            QMessageBox.warning(self, "Database Error", "Database not loaded.")
            return

        if self.mass_mode_radio.isChecked():
            self.perform_mass_search()
        else:
            self.perform_formula_search()

    def perform_mass_search(self):
        """Batch mass search with multiple adducts."""
        text = self.mass_input.toPlainText().strip()
        tol_text = self.tolerance_input.text().strip()

        if not text:
            QMessageBox.warning(self, "Input Error", "Enter at least one mass.")
            return

        # Parse masses
        mass_strings = re.split(r'[,\n\s]+', text)
        masses = []
        for s in mass_strings:
            s = s.strip()
            if s:
                try:
                    masses.append(float(s))
                except ValueError:
                    QMessageBox.warning(self, "Input Error", f"Invalid mass: '{s}'")
                    return

        if not masses:
            QMessageBox.warning(self, "Input Error", "No valid masses entered.")
            return

        try:
            tolerance = float(tol_text) if tol_text else 0.5
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Invalid tolerance.")
            return

        selected_adducts = self.get_selected_adducts()
        if not selected_adducts:
            QMessageBox.warning(self, "Input Error", "Select at least one adduct.")
            return

        top_n = self.mass_top_n_spin.value()

        # Build all mass/adduct pairs
        pairs = []
        for mass in masses:
            for label, delta in selected_adducts:
                pairs.append((mass, delta, label))

        self.update_status(f"Searching {len(masses)} masses × {len(selected_adducts)} adducts...")

        try:
            source_filter = self.get_selected_sources()
            results = self.search_engine.search_batch_masses(
                pairs, tolerance, source_filter, max_results_per_query=top_n
            )

            self.last_results = results
            self.last_search_params = {
                'type': 'mass',
                'masses': masses,
                'tolerance': tolerance,
                'adducts': [label for label, _ in selected_adducts],
                'top_n': top_n
            }

            self.display_results(results)
            self.update_status(
                f"Found {len(results)} total matches "
                f"({len(masses)} masses × {len(selected_adducts)} adducts, top {top_n} each)"
            )
        except Exception as e:
            QMessageBox.critical(self, "Search Error", str(e))

    def perform_formula_search(self):
        """Batch formula search."""
        text = self.formula_input.toPlainText().strip()

        if not text:
            QMessageBox.warning(self, "Input Error", "Enter at least one formula.")
            return

        # Parse formulas
        formula_strings = re.split(r'[,\n]+', text)
        formulas = [f.strip() for f in formula_strings if f.strip()]

        if not formulas:
            QMessageBox.warning(self, "Input Error", "No valid formulas entered.")
            return

        top_n = self.formula_top_n_spin.value()

        self.update_status(f"Searching {len(formulas)} formulas...")

        try:
            source_filter = self.get_selected_sources()
            all_results = []

            for query_id, formula in enumerate(formulas):
                results = self.search_engine.search_by_formula(formula, source_filter, max_results=top_n)

                for r in results:
                    r['adduct'] = "N/A"
                    r['mass_error'] = None
                    r['ppm_error'] = None
                    r['neutral_mass'] = r.get('exact_mass')
                    r['query_id'] = query_id
                    r['query_mass'] = formula
                    r['query_adduct'] = ""

                all_results.extend(results)

            self.last_results = all_results
            self.last_search_params = {
                'type': 'formula',
                'formulas': formulas,
                'top_n': top_n
            }

            self.display_results(all_results)
            self.update_status(f"Found {len(all_results)} total matches ({len(formulas)} formulas, top {top_n} each)")
        except Exception as e:
            QMessageBox.critical(self, "Search Error", str(e))

    def build_source_url(self, source, source_id):
        template = SOURCE_URLS.get(source)
        if not template or not source_id:
            return source_id or ""
        return template.format(id=source_id)

    def display_results(self, results):
        self.results_table.setRowCount(0)

        if not results:
            self.export_button.setEnabled(False)
            self.copy_button.setEnabled(False)
            return

        # Group by query_id
        grouped = {}
        for r in results:
            qid = r.get('query_id', 0)
            if qid not in grouped:
                grouped[qid] = []
            grouped[qid].append(r)

        total_rows = len(results) + len(grouped)
        self.results_table.setRowCount(total_rows)

        current_row = 0

        for qid in sorted(grouped.keys()):
            group_results = grouped[qid]
            first = group_results[0]

            query_mass = first.get('query_mass', '')
            if isinstance(query_mass, float):
                query_label = f"{query_mass:.4f} Da"
            else:
                query_label = str(query_mass)

            query_adduct = first.get('query_adduct', first.get('adduct', ''))

            # Separator row
            if query_adduct:
                separator_text = f"═══  Query {qid + 1}: {query_label} | {query_adduct}  ═══  ({len(group_results)} results)"
            else:
                separator_text = f"═══  Query {qid + 1}: {query_label}  ═══  ({len(group_results)} results)"

            separator_item = QTableWidgetItem(separator_text)
            separator_item.setBackground(QColor(200, 200, 200))
            separator_item.setForeground(QColor(0, 0, 0))
            sep_font = separator_item.font()
            sep_font.setBold(True)
            separator_item.setFont(sep_font)

            self.results_table.setItem(current_row, 0, separator_item)
            self.results_table.setSpan(current_row, 0, 1, 8)  # Span 8 columns
            current_row += 1

            # Results
            for r in group_results:
                source = r.get('source', '')
                source_id = r.get('source_id', '')
                url = self.build_source_url(source, source_id)
                mass = r.get('neutral_mass') or r.get('exact_mass', '')
                err_da = r.get('mass_error')
                err_ppm = r.get('ppm_error')
                adduct = r.get('adduct', '')

                cells = [
                    r.get('name', ''),
                    r.get('formula', 'N/A'),
                    str(mass) if mass != '' else '',
                    str(err_da) if err_da is not None else '—',
                    str(err_ppm) if err_ppm is not None else '—',
                    adduct,
                    source,
                    url,
                ]

                row_color = SOURCE_COLORS.get(source, QColor(255, 255, 255))

                for j, text in enumerate(cells):
                    item = QTableWidgetItem(text)
                    item.setBackground(row_color)
                    item.setForeground(QColor(0, 0, 0))
                    if j == 7:  # URL column (now index 7)
                        item.setForeground(QColor(0, 60, 160))
                        f = item.font()
                        f.setItalic(True)
                        item.setFont(f)
                    self.results_table.setItem(current_row, j, item)

                current_row += 1

        self.export_button.setEnabled(True)
        self.copy_button.setEnabled(False)

    def on_selection_changed(self):
        self.copy_button.setEnabled(bool(self.results_table.selectedItems()))

    def copy_selected_row(self):
        selected = self.results_table.selectedItems()
        if not selected:
            return

        row = self.results_table.currentRow()
        cols = self.results_table.columnCount()
        parts = [self.results_table.item(row, c).text() for c in range(cols)
                 if self.results_table.item(row, c)]

        QApplication.clipboard().setText('\t'.join(parts))
        self.update_status(f"Row {row + 1} copied to clipboard")

    def export_to_csv(self):
        if not self.last_results:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "mass_lookup_results.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                p = self.last_search_params
                if p.get('type') == 'mass':
                    writer.writerow([
                        f"# Mass Search — {len(p['masses'])} masses × {len(p['adducts'])} adducts | "
                        f"Tolerance: ±{p['tolerance']} Da | Top {p['top_n']} per query"
                    ])
                    writer.writerow([f"# Masses: {', '.join(map(str, p['masses']))}"])
                    writer.writerow([f"# Adducts: {', '.join(p['adducts'])}"])
                else:
                    writer.writerow([
                        f"# Formula Search — {len(p['formulas'])} formulas | Top {p['top_n']} per formula"
                    ])
                    writer.writerow([f"# Formulas: {', '.join(p['formulas'])}"])

                writer.writerow([])
                writer.writerow([
                    "Query", "Adduct", "Name", "Formula", "Exact Mass (Da)",
                    "Error (Da)", "Error (ppm)", "Source Database", "Source ID", "Source URL"
                ])

                for r in self.last_results:
                    query_mass = r.get('query_mass', '')
                    source = r.get('source', '')
                    source_id = r.get('source_id', '')

                    writer.writerow([
                        query_mass,
                        r.get('adduct', r.get('query_adduct', '')),
                        r.get('name', ''),
                        r.get('formula', ''),
                        r.get('neutral_mass') or r.get('exact_mass', ''),
                        r.get('mass_error', ''),
                        r.get('ppm_error', ''),
                        source,
                        source_id,
                        self.build_source_url(source, source_id),
                    ])

            QMessageBox.information(self, "Export Successful", f"Saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def clear_search(self):
        self.mass_input.clear()
        self.tolerance_input.setText("0.5")
        self.formula_input.clear()
        self.results_table.setRowCount(0)
        self.last_results = []
        self.last_search_params = {}
        self.export_button.setEnabled(False)
        self.copy_button.setEnabled(False)

        if self.db_loaded:
            parts = [f"{s}: {c:,}" for s, c in self.stats["by_source"].items()]
            self.update_status("Database loaded — " + " | ".join(parts))

    def update_status(self, msg):
        self.status_label.setText(msg)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    w = MassLookupWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()