"""
Mass Lookup Tool - Main GUI Window v3
======================================

Full-featured desktop application with:
- Mass search with expanded adduct support (H, Na, K, NH4)
- Formula search
- Database filter checkboxes
- Source URL display (copyable)
- Copy row to clipboard
- CSV export

Usage:
    python main.py
"""

import sys
import csv
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QMessageBox, QHeaderView, QRadioButton, QButtonGroup,
    QComboBox, QFileDialog, QCheckBox, QAbstractItemView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from search.search_engine import SearchEngine


# ─────────────────────────────────────────────
#  ADDUCT DEFINITIONS
# ─────────────────────────────────────────────

ADDUCTS = {
    # Label                   : (mass_delta, mode)
    "Neutral (exact mass)"    : (0.0,        "neutral"),
    "[M+H]⁺  (+1.00728)"     : (1.007276,   "positive"),
    "[M+Na]⁺ (+22.98922)"    : (22.989218,  "positive"),
    "[M+K]⁺  (+38.96316)"    : (38.963158,  "positive"),
    "[M+NH4]⁺ (+18.03437)"   : (18.034374,  "positive"),
    "[M-H]⁻  (-1.00728)"     : (-1.007276,  "negative"),
    "[M+Cl]⁻ (+34.96940)"    : (34.969402,  "negative"),
    "[M+FA-H]⁻ (+44.99820)"  : (44.998201,  "negative"),
}

# Source URL templates — shown as copyable text
SOURCE_URLS = {
    "HMDB"     : "https://hmdb.ca/metabolites/{id}",
    "ChEBI"    : "https://www.ebi.ac.uk/chebi/searchId.do?chebiId={id}",
    "LipidMaps": "https://www.lipidmaps.org/databases/lmsd/{id}",
}

# Source display colors for the table
SOURCE_COLORS = {
    "HMDB"     : QColor(220, 240, 255),   # Light blue
    "ChEBI"    : QColor(220, 255, 220),   # Light green
    "LipidMaps": QColor(255, 240, 220),   # Light orange
}


class MassLookupWindow(QMainWindow):
    """Main application window — v3."""

    def __init__(self):
        super().__init__()

        # Initialize search engine
        try:
            self.search_engine = SearchEngine()
            self.stats         = self.search_engine.get_stats()
            self.db_loaded     = True
        except FileNotFoundError as e:
            self.db_loaded = False
            self.stats     = {}
            QMessageBox.critical(self, "Database Error", str(e))

        self.last_results      = []
        self.last_search_params = {}

        self.init_ui()

        if self.db_loaded:
            parts = [f"{src}: {cnt:,}" for src, cnt in self.stats["by_source"].items()]
            self.update_status("Database loaded — " + " | ".join(parts))

    # ─────────────────────────────────────────
    #  UI CONSTRUCTION
    # ─────────────────────────────────────────

    def init_ui(self):
        self.setWindowTitle("LC-MS Mass Lookup Tool")
        self.setGeometry(100, 100, 1350, 800)

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

        self.mode_group        = QButtonGroup()
        self.mass_mode_radio   = QRadioButton("Mass")
        self.formula_mode_radio = QRadioButton("Formula")
        self.mass_mode_radio.setChecked(True)
        self.mode_group.addButton(self.mass_mode_radio)
        self.mode_group.addButton(self.formula_mode_radio)
        self.mass_mode_radio.toggled.connect(self.on_mode_changed)

        mode_row.addWidget(self.mass_mode_radio)
        mode_row.addWidget(self.formula_mode_radio)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # ── Input row ────────────────────────
        input_row = QHBoxLayout()

        # Mass inputs
        self.mass_label = QLabel("Observed Mass (Da):")
        input_row.addWidget(self.mass_label)

        self.mass_input = QLineEdit()
        self.mass_input.setPlaceholderText("e.g., 181.071")
        self.mass_input.returnPressed.connect(self.perform_search)
        input_row.addWidget(self.mass_input)

        self.tol_label = QLabel("Tolerance (±):")
        input_row.addWidget(self.tol_label)

        self.tolerance_input = QLineEdit()
        self.tolerance_input.setText("0.5")
        self.tolerance_input.setMaximumWidth(80)
        self.tolerance_input.returnPressed.connect(self.perform_search)
        input_row.addWidget(self.tolerance_input)

        self.tol_unit_label = QLabel("Da")
        input_row.addWidget(self.tol_unit_label)

        # Formula inputs (hidden by default)
        self.formula_label = QLabel("Molecular Formula:")
        self.formula_label.hide()
        input_row.addWidget(self.formula_label)

        self.formula_input = QLineEdit()
        self.formula_input.setPlaceholderText("e.g., C6H12O6")
        self.formula_input.returnPressed.connect(self.perform_search)
        self.formula_input.hide()
        input_row.addWidget(self.formula_input)

        input_row.addStretch()
        layout.addLayout(input_row)

        # ── Adduct row ───────────────────────
        adduct_row = QHBoxLayout()
        self.adduct_label = QLabel("Adduct / Ion Mode:")
        adduct_row.addWidget(self.adduct_label)

        self.adduct_combo = QComboBox()
        for label in ADDUCTS.keys():
            self.adduct_combo.addItem(label)
        self.adduct_combo.setMinimumWidth(250)
        adduct_row.addWidget(self.adduct_combo)
        adduct_row.addStretch()
        layout.addLayout(adduct_row)

        # ── Button row ───────────────────────
        btn_row = QHBoxLayout()

        self.search_button = QPushButton("Search")
        self.search_button.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "padding: 8px 20px; font-weight: bold; }"
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
        """Database filter checkboxes."""
        group  = QGroupBox("Database Filter  (uncheck to exclude a source)")
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

        self.results_table.setAlternatingRowColors(False)   # We use custom row colors
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.results_table.itemSelectionChanged.connect(self.on_selection_changed)

        hdr = self.results_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(7, QHeaderView.ResizeToContents)

        layout.addWidget(self.results_table)
        group.setLayout(layout)
        return group

    def create_status_bar(self):
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("QLabel { padding: 5px; }")
        return self.status_label

    # ─────────────────────────────────────────
    #  MODE SWITCHING
    # ─────────────────────────────────────────

    def on_mode_changed(self):
        mass_mode = self.mass_mode_radio.isChecked()

        for w in [self.mass_label, self.mass_input,
                  self.tol_label, self.tolerance_input, self.tol_unit_label,
                  self.adduct_label, self.adduct_combo]:
            w.setVisible(mass_mode)

        for w in [self.formula_label, self.formula_input]:
            w.setVisible(not mass_mode)

        (self.mass_input if mass_mode else self.formula_input).setFocus()

    # ─────────────────────────────────────────
    #  SEARCH
    # ─────────────────────────────────────────

    def get_selected_sources(self):
        """Return list of checked database sources, or None (= all) if all checked."""
        selected = [src for src, cb in self.db_checkboxes.items() if cb.isChecked()]
        return selected if selected else None

    def perform_search(self):
        if not self.db_loaded:
            QMessageBox.warning(self, "Database Error", "Database is not loaded.")
            return

        if self.mass_mode_radio.isChecked():
            self.perform_mass_search()
        else:
            self.perform_formula_search()

    def perform_mass_search(self):
        mass_text = self.mass_input.text().strip()
        tol_text  = self.tolerance_input.text().strip()

        if not mass_text:
            QMessageBox.warning(self, "Input Error", "Please enter a target mass.")
            return

        try:
            target_mass = float(mass_text)
        except ValueError:
            QMessageBox.warning(self, "Input Error", f"Invalid mass: '{mass_text}'")
            return

        try:
            tolerance = float(tol_text) if tol_text else 0.5
        except ValueError:
            QMessageBox.warning(self, "Input Error", f"Invalid tolerance: '{tol_text}'")
            return

        # Get adduct
        adduct_label  = self.adduct_combo.currentText()
        mass_delta, _ = ADDUCTS[adduct_label]

        # Neutral mass = observed mass − adduct delta
        neutral_mass  = target_mass - mass_delta

        self.update_status(f"Searching {target_mass} Da  ({adduct_label})  ± {tolerance} Da...")

        try:
            source_filter = self.get_selected_sources()
            results = self.search_engine.search_by_mass(
                neutral_mass, tolerance, ion_mode='neutral',
                source_filter=source_filter
            )
            # Tag each result with the adduct label and original observed mass
            for r in results:
                r['adduct']        = adduct_label
                r['observed_mass'] = target_mass

            self.last_results      = results
            self.last_search_params = {
                'type': 'mass', 'observed_mass': target_mass,
                'neutral_mass': neutral_mass, 'tolerance': tolerance,
                'adduct': adduct_label
            }
            self.display_results(results)
            self.update_status(
                f"Found {len(results):,} matches for {target_mass} Da "
                f"({adduct_label}) ± {tolerance} Da"
            )
        except Exception as e:
            QMessageBox.critical(self, "Search Error", str(e))

    def perform_formula_search(self):
        formula = self.formula_input.text().strip()

        if not formula:
            QMessageBox.warning(self, "Input Error", "Please enter a molecular formula.")
            return

        self.update_status(f"Searching for formula: {formula}...")

        try:
            source_filter = self.get_selected_sources()
            results = self.search_engine.search_by_formula(formula, source_filter=source_filter)

            for r in results:
                r['adduct']       = "N/A"
                r['mass_error']   = None
                r['ppm_error']    = None
                r['neutral_mass'] = r.get('exact_mass')

            self.last_results      = results
            self.last_search_params = {'type': 'formula', 'formula': formula}
            self.display_results(results)
            self.update_status(f"Found {len(results):,} matches for formula: {formula}")
        except Exception as e:
            QMessageBox.critical(self, "Search Error", str(e))

    # ─────────────────────────────────────────
    #  DISPLAY
    # ─────────────────────────────────────────

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

        self.results_table.setRowCount(len(results))
        row_color = QColor(255, 255, 255)

        for i, r in enumerate(results):
            source    = r.get('source', '')
            source_id = r.get('source_id', '')
            url       = self.build_source_url(source, source_id)
            mass      = r.get('neutral_mass') or r.get('exact_mass', '')
            err_da    = r.get('mass_error')
            err_ppm   = r.get('ppm_error')
            adduct    = r.get('adduct', '')

            cells = [
                r.get('name', ''),
                r.get('formula', 'N/A'),
                str(mass) if mass != '' else '',
                str(err_da)  if err_da  is not None else '—',
                str(err_ppm) if err_ppm is not None else '—',
                adduct,
                source,
                url,
            ]

            row_color = SOURCE_COLORS.get(source, QColor(255, 255, 255))

            for j, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setBackground(row_color)
                item.setForeground(QColor(0, 0, 0))  # Always black text
                if j == 7:  # URL column - dark blue italic but still readable
                    item.setForeground(QColor(0, 60, 160))
                    f = item.font()
                    f.setItalic(True)
                    item.setFont(f)
                self.results_table.setItem(i, j, item)

        self.export_button.setEnabled(True)
        self.copy_button.setEnabled(False)   # Enable only when row selected

    # ─────────────────────────────────────────
    #  COPY / EXPORT
    # ─────────────────────────────────────────

    def on_selection_changed(self):
        self.copy_button.setEnabled(bool(self.results_table.selectedItems()))

    def copy_selected_row(self):
        """Copy selected row as tab-separated text to clipboard."""
        selected = self.results_table.selectedItems()
        if not selected:
            return

        row    = self.results_table.currentRow()
        cols   = self.results_table.columnCount()
        parts  = [self.results_table.item(row, c).text() for c in range(cols)
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
                        f"# Mass Search — Observed: {p['observed_mass']} Da | "
                        f"Adduct: {p['adduct']} | "
                        f"Neutral: {p['neutral_mass']:.4f} Da | "
                        f"Tolerance: ±{p['tolerance']} Da"
                    ])
                else:
                    writer.writerow([f"# Formula Search — {p.get('formula', '')}"])

                writer.writerow([])
                writer.writerow([
                    "Name", "Formula", "Exact Mass (Da)", "Error (Da)",
                    "Error (ppm)", "Adduct", "Source Database", "Source ID", "Source URL"
                ])

                for r in self.last_results:
                    source    = r.get('source', '')
                    source_id = r.get('source_id', '')
                    writer.writerow([
                        r.get('name', ''),
                        r.get('formula', ''),
                        r.get('neutral_mass') or r.get('exact_mass', ''),
                        r.get('mass_error', ''),
                        r.get('ppm_error', ''),
                        r.get('adduct', ''),
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
        self.last_results       = []
        self.last_search_params = {}
        self.export_button.setEnabled(False)
        self.copy_button.setEnabled(False)

        if self.db_loaded:
            parts = [f"{s}: {c:,}" for s, c in self.stats["by_source"].items()]
            self.update_status("Database loaded — " + " | ".join(parts))

        (self.mass_input if self.mass_mode_radio.isChecked() else self.formula_input).setFocus()

    def update_status(self, msg):
        self.status_label.setText(msg)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    w = MassLookupWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()