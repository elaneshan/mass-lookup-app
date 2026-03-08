"""
LUCID — LC-MS Unified Compound Identification Database
"""

import sys
import csv
import re
import configparser
from pathlib import Path

import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QMessageBox, QHeaderView, QRadioButton, QButtonGroup,
    QFileDialog, QCheckBox, QAbstractItemView, QTextEdit,
    QSpinBox, QShortcut, QFrame
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QColor, QKeySequence, QDesktopServices, QIcon


# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────

def load_config():
    config = configparser.ConfigParser()
    base_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) \
               else Path(__file__).parent
    config_path = base_dir / 'config.ini'
    if config_path.exists():
        config.read(config_path)
    else:
        config['server'] = {'url': 'http://localhost:8000'}
        config['app']    = {'mode': 'local'}
        with open(config_path, 'w') as f:
            config.write(f)
    mode       = config.get('app',    'mode', fallback='local').strip().lower()
    server_url = config.get('server', 'url',  fallback='http://localhost:8000').strip().rstrip('/')
    return mode, server_url


MODE, SERVER_URL = load_config()


# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────

ADDUCTS = {
    "Neutral (exact mass)"   : (0.0,        "neutral",  "neutral"),
    "[M+H]⁺  (+1.00728)"    : (1.007276,   "positive", "[M+H]+"),
    "[M+Na]⁺ (+22.98922)"   : (22.989218,  "positive", "[M+Na]+"),
    "[M+K]⁺  (+38.96316)"   : (38.963158,  "positive", "[M+K]+"),
    "[M+NH4]⁺ (+18.03437)"  : (18.034374,  "positive", "[M+NH4]+"),
    "[M-H]⁻  (-1.00728)"    : (-1.007276,  "negative", "[M-H]-"),
    "[M+Cl]⁻ (+34.96940)"   : (34.969402,  "negative", "[M+Cl]-"),
    "[M+FA-H]⁻ (+44.99820)" : (44.998201,  "negative", "[M+FA-H]-"),
}

SOURCE_URLS = {
    "HMDB"     : "https://hmdb.ca/metabolites/{id}",
    "ChEBI"    : "https://www.ebi.ac.uk/chebi/searchId.do?chebiId={id}",
    "LipidMaps": "https://www.lipidmaps.org/databases/lmsd/{id}",
    "NPAtlas"  : "https://www.npatlas.org/explore/compounds/{id}",
}

PUBCHEM_URL = "https://pubchem.ncbi.nlm.nih.gov/#query={inchikey}"

SOURCE_COLORS = {
    "HMDB"     : QColor(220, 240, 255),
    "ChEBI"    : QColor(220, 255, 220),
    "LipidMaps": QColor(255, 240, 220),
    "NPAtlas"  : QColor(240, 220, 255),
}

COL_NAME     = 0
COL_FORMULA  = 1
COL_MASS     = 2
COL_ERR_DA   = 3
COL_ERR_PPM  = 4
COL_ADDUCT   = 5
COL_SOURCE   = 6
COL_URL      = 7
COL_INCHIKEY = 8
TOTAL_COLS   = 9


# ─────────────────────────────────────────────
#  API CLIENT
# ─────────────────────────────────────────────

class APIClient:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session  = requests.Session()
        self.session.timeout = 15

    def get_stats(self):
        resp = self.session.get(f"{self.base_url}/stats")
        resp.raise_for_status()
        return resp.json()

    def search_by_mass(self, target_mass, tolerance=0.5, ion_mode='neutral',
                       source_filter=None, max_results=20):
        adduct_map = {'positive': '[M+H]+', 'negative': '[M-H]-', 'neutral': 'neutral'}
        params = {'mass': target_mass, 'tolerance': tolerance,
                  'adduct': adduct_map.get(ion_mode, 'neutral'), 'limit': max_results}
        if source_filter:
            params['sources'] = ','.join(source_filter)
        resp = self.session.get(f"{self.base_url}/search/mass", params=params)
        resp.raise_for_status()
        return [{'source': r.get('source', ''), 'source_id': r.get('source_id', ''),
                 'name': r.get('name', ''), 'formula': r.get('formula') or 'N/A',
                 'cas': r.get('cas') or '', 'inchikey': r.get('inchikey') or '',
                 'neutral_mass': r.get('exact_mass', 0), 'observed_mass': target_mass,
                 'mass_error': r.get('mass_error', 0), 'ppm_error': r.get('ppm_error', 0),
                 'ion_mode': ion_mode} for r in resp.json()]

    def search_batch_masses(self, mass_adduct_pairs, tolerance=0.5,
                            source_filter=None, max_results_per_query=20):
        masses = list({p[0] for p in mass_adduct_pairs})
        adduct_api_map = {label: api for label, (_, _, api) in ADDUCTS.items()}
        api_adducts = list({adduct_api_map.get(p[2], p[2]) for p in mass_adduct_pairs})
        body = {'masses': masses, 'adducts': api_adducts,
                'tolerance': tolerance, 'limit': max_results_per_query}
        if source_filter:
            body['sources'] = source_filter
        resp = self.session.post(f"{self.base_url}/search/batch", json=body)
        resp.raise_for_status()
        all_results = []
        for query_id, query in enumerate(resp.json()):
            qmass  = query['query_mass']
            adduct = query['adduct']
            for r in query['results']:
                all_results.append({
                    'query_id': query_id, 'query_mass': qmass,
                    'query_adduct': adduct, 'adduct': adduct,
                    'source': r.get('source', ''), 'source_id': r.get('source_id', ''),
                    'name': r.get('name', ''), 'formula': r.get('formula') or 'N/A',
                    'cas': r.get('cas') or '', 'inchikey': r.get('inchikey') or '',
                    'neutral_mass': r.get('exact_mass', 0), 'observed_mass': qmass,
                    'mass_error': r.get('mass_error', 0), 'ppm_error': r.get('ppm_error', 0),
                    'ion_mode': 'neutral'})
        return all_results

    def search_by_formula(self, formula, source_filter=None, max_results=100):
        params = {'formula': formula, 'limit': max_results}
        if source_filter:
            params['sources'] = ','.join(source_filter)
        resp = self.session.get(f"{self.base_url}/search/formula", params=params)
        resp.raise_for_status()
        return [{'source': r.get('source', ''), 'source_id': r.get('source_id', ''),
                 'name': r.get('name', ''), 'formula': r.get('formula') or 'N/A',
                 'cas': r.get('cas') or '', 'inchikey': r.get('inchikey') or '',
                 'exact_mass': r.get('exact_mass', 0)} for r in resp.json()]


# ─────────────────────────────────────────────
#  CLICKABLE URL ITEM
# ─────────────────────────────────────────────

class ClickableURLItem(QTableWidgetItem):
    def __init__(self, url):
        super().__init__(url)
        self.setForeground(QColor(0, 60, 160))
        f = self.font()
        f.setUnderline(True)
        self.setFont(f)
        self.setToolTip("Click to open in browser")


# ─────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────

class MassLookupWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.db_loaded         = False
        self.stats             = {}
        self._all_results_rows = []
        self.last_results      = []
        self.last_search_params = {}

        if MODE == 'api':
            try:
                self.search_engine = APIClient(SERVER_URL)
                self.stats         = self.search_engine.get_stats()
                self.db_loaded     = True
                self.backend_label = "API"
            except Exception as e:
                QMessageBox.critical(self, "Connection Error",
                    f"Could not connect to server:\n{SERVER_URL}\n\n{e}")
        else:
            try:
                from search.search_engine import SearchEngine
                self.search_engine = SearchEngine()
                self.stats         = self.search_engine.get_stats()
                self.db_loaded     = True
                self.backend_label = "Local DB"
            except ModuleNotFoundError:
                # Packaged exe shipped with mode=local by mistake — show helpful message
                QMessageBox.critical(self, "Configuration Error",
                    "This application is configured for local mode but no local database "
                    "was found.\n\nIf you received this as a distributed .exe, please "
                    "contact the person who shared it — the config.ini may need to be "
                    "updated to mode = api.")
            except FileNotFoundError as e:
                QMessageBox.critical(self, "Database Error", str(e))
            except Exception as e:
                QMessageBox.critical(self, "Local DB Error", str(e))

        self.init_ui()

        if self.db_loaded:
            parts = [f"{src}: {cnt:,}" for src, cnt in self.stats["by_source"].items()]
            self.update_status(
                f"Backend: {self.backend_label}     " + "     ".join(parts))

    def init_ui(self):
        self.setWindowTitle("LUCID — LC-MS Unified Compound Identification Database")

        # Set window icon (works both in dev and PyInstaller exe)
        icon_path = Path(sys.executable).parent / "lucid.ico" if getattr(sys, "frozen", False)                     else Path(__file__).parent / "lucid.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setGeometry(100, 100, 1500, 950)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout()
        central.setLayout(outer)

        # Top controls (fixed height)
        top_widget = QWidget()
        top_layout = QVBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_widget.setLayout(top_layout)
        top_layout.addWidget(self.create_search_panel())
        top_layout.addWidget(self.create_db_filter_panel())
        top_layout.addWidget(self.create_filter_bar())

        self.top_widget    = top_widget
        self._expanded     = False

        outer.addWidget(top_widget)
        outer.addWidget(self.create_results_panel())
        outer.setStretch(0, 0)   # search panel fixed
        outer.setStretch(1, 1)   # results expands
        outer.addWidget(self.create_status_bar())

        QShortcut(QKeySequence("Ctrl+F"), self, self.focus_filter_bar)

    # ── Search panel ─────────────────────────

    def create_search_panel(self):
        group  = QGroupBox("Search Parameters")
        layout = QVBoxLayout()

        # Mode row
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
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

        # Mass input
        self.mass_label = QLabel("Observed Masses (one per line or comma-separated):")
        layout.addWidget(self.mass_label)
        self.mass_input = QTextEdit()
        self.mass_input.setPlaceholderText("181.071\n194.079\n342.116\n\nOr: 181.071, 194.079")
        self.mass_input.setMaximumHeight(80)
        layout.addWidget(self.mass_input)

        mass_params_row = QHBoxLayout()
        mass_params_row.addWidget(QLabel("Tolerance (±):"))
        self.tolerance_input = QLineEdit("0.5")
        self.tolerance_input.setMaximumWidth(70)
        mass_params_row.addWidget(self.tolerance_input)
        mass_params_row.addWidget(QLabel("Da"))
        mass_params_row.addWidget(QLabel("   Max results per query:"))
        self.mass_top_n_spin = QSpinBox()
        self.mass_top_n_spin.setMinimum(1)
        self.mass_top_n_spin.setMaximum(500)
        self.mass_top_n_spin.setValue(20)
        self.mass_top_n_spin.setMaximumWidth(70)
        mass_params_row.addWidget(self.mass_top_n_spin)
        mass_params_row.addStretch()
        self.tol_label      = self.tolerance_input   # keep refs for show/hide
        self.tol_unit_label = QLabel("Da")
        self.mass_top_n_label = QLabel("Max results per query:")
        layout.addLayout(mass_params_row)

        # Formula input
        self.formula_label = QLabel("Molecular Formulas (one per line or comma-separated):")
        self.formula_label.hide()
        layout.addWidget(self.formula_label)
        self.formula_input = QTextEdit()
        self.formula_input.setPlaceholderText("C6H12O6\nC12H22O11")
        self.formula_input.setMaximumHeight(80)
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
        self.formula_top_n_spin.setMaximumWidth(70)
        self.formula_top_n_spin.hide()
        formula_params_row.addWidget(self.formula_top_n_spin)
        formula_params_row.addStretch()
        layout.addLayout(formula_params_row)

        # Adducts
        self.adduct_group = QGroupBox("Adducts")
        adduct_layout     = QVBoxLayout()
        self.adduct_checkboxes = {}
        col1 = QVBoxLayout()
        col2 = QVBoxLayout()
        keys = list(ADDUCTS.keys())
        mid  = len(keys) // 2
        for i, label in enumerate(keys):
            cb = QCheckBox(label)
            if label == "[M+H]⁺  (+1.00728)":
                cb.setChecked(True)
            self.adduct_checkboxes[label] = cb
            (col1 if i < mid else col2).addWidget(cb)
        row = QHBoxLayout()
        row.addLayout(col1)
        row.addLayout(col2)
        row.addStretch()
        adduct_layout.addLayout(row)
        self.adduct_group.setLayout(adduct_layout)
        layout.addWidget(self.adduct_group)

        # Buttons
        btn_row = QHBoxLayout()
        self.search_button = QPushButton("Search")
        self.search_button.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "padding: 8px 22px; font-weight: bold; font-size: 13px; }")
        self.search_button.clicked.connect(self.perform_search)
        btn_row.addWidget(self.search_button)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_search)
        btn_row.addWidget(self.clear_button)
        self.copy_button = QPushButton("Copy Row")
        self.copy_button.clicked.connect(self.copy_selected_row)
        self.copy_button.setEnabled(False)
        btn_row.addWidget(self.copy_button)
        self.export_button = QPushButton("Export CSV")
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
        sources = list(self.stats.get("by_source", {}).keys()) or \
                  ["HMDB", "ChEBI", "LipidMaps", "NPAtlas"]
        # Large sources unchecked by default — slow search times
        large_sources = {"PubChem", "MS-DIAL"}
        for source in sources:
            count = self.stats.get("by_source", {}).get(source, 0)
            cb    = QCheckBox(f"{source}  ({count:,})")
            cb.setChecked(source not in large_sources)
            if source in large_sources:
                cb.setStyleSheet("color: #888;")
                cb.setToolTip("Large database — may increase search time. Check to include.")
            self.db_checkboxes[source] = cb
            layout.addWidget(cb)
        layout.addStretch()
        group.setLayout(layout)
        return group

    def create_filter_bar(self):
        frame  = QFrame()
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(QLabel("Filter results (Ctrl+F):"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText(
            "Filter by name, formula, source, InChIKey...")
        self.filter_input.setMaximumWidth(450)
        self.filter_input.textChanged.connect(self.apply_filter)
        layout.addWidget(self.filter_input)
        clear_btn = QPushButton("Clear")
        clear_btn.setMaximumWidth(50)
        clear_btn.clicked.connect(self.clear_filter)
        layout.addWidget(clear_btn)
        layout.addStretch()
        frame.setLayout(layout)
        return frame

    def focus_filter_bar(self):
        self.filter_input.setFocus()
        self.filter_input.selectAll()

    def apply_filter(self):
        term = self.filter_input.text().strip().lower()
        for row_idx, row_data in self._all_results_rows:
            hidden = bool(term) and not any(
                term in str(v).lower() for v in row_data.values())
            self.results_table.setRowHidden(row_idx, hidden)

    def clear_filter(self):
        self.filter_input.clear()

    def create_results_panel(self):
        group  = QGroupBox("Results  —  click a URL to open in browser")
        layout = QVBoxLayout()

        # Expand button row
        btn_row = QHBoxLayout()
        self.expand_button = QPushButton("Expand Results")
        self.expand_button.setMaximumWidth(130)
        self.expand_button.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        self.expand_button.clicked.connect(self.toggle_expand)
        btn_row.addWidget(self.expand_button)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(TOTAL_COLS)
        self.results_table.setHorizontalHeaderLabels([
            "Name", "Formula", "Exact Mass (Da)",
            "Error (Da)", "Error (ppm)", "Adduct",
            "Source", "Source URL", "InChIKey"
        ])
        self.results_table.setAlternatingRowColors(False)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        # Allow extended selection so users can highlight/select text with mouse
        self.results_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.results_table.itemSelectionChanged.connect(self.on_selection_changed)
        self.results_table.cellClicked.connect(self.on_cell_clicked)
        hdr = self.results_table.horizontalHeader()
        hdr.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        for col in range(1, TOTAL_COLS):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        layout.addWidget(self.results_table)
        group.setLayout(layout)
        return group

    def on_cell_clicked(self, row, col):
        if col == COL_URL:
            item = self.results_table.item(row, col)
            if item and item.text().startswith("http"):
                QDesktopServices.openUrl(QUrl(item.text()))

    def create_status_bar(self):
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(
            "QLabel { padding: 4px; color: #111111; font-size: 12px; }")
        return self.status_label

    def toggle_expand(self):
        self._expanded = not self._expanded
        self.top_widget.setVisible(not self._expanded)
        self.expand_button.setText(
            "Collapse Results" if self._expanded else "Expand Results")

    # ── Helpers ──────────────────────────────

    def on_mode_changed(self):
        is_mass = self.mass_mode_radio.isChecked()
        for w in [self.mass_label, self.mass_input, self.adduct_group]:
            w.setVisible(is_mass)
        for w in [self.formula_label, self.formula_input,
                  self.formula_top_n_label, self.formula_top_n_spin]:
            w.setVisible(not is_mass)
        (self.mass_input if is_mass else self.formula_input).setFocus()

    def get_selected_sources(self):
        selected = [src for src, cb in self.db_checkboxes.items() if cb.isChecked()]
        return selected if selected else None

    def get_selected_adducts(self):
        return [(label, delta, api_label)
                for label, cb in self.adduct_checkboxes.items()
                if cb.isChecked()
                for delta, _, api_label in [ADDUCTS[label]]]

    # ── Search ───────────────────────────────

    def perform_search(self):
        if not self.db_loaded:
            QMessageBox.warning(self, "Not Connected", "No database or server connected.")
            return
        self.clear_filter()
        if self.mass_mode_radio.isChecked():
            self.perform_mass_search()
        else:
            self.perform_formula_search()

    def perform_mass_search(self):
        text     = self.mass_input.toPlainText().strip()
        tol_text = self.tolerance_input.text().strip()
        if not text:
            QMessageBox.warning(self, "Input Error", "Enter at least one mass.")
            return
        masses = []
        for s in re.split(r'[,\n\s]+', text):
            s = s.strip()
            if s:
                try:
                    masses.append(float(s))
                except ValueError:
                    QMessageBox.warning(self, "Input Error", f"Invalid mass: '{s}'")
                    return
        if not masses:
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
        pairs = [(mass, delta, label)
                 for mass in masses
                 for label, delta, _ in selected_adducts]
        self.update_status(
            f"Searching {len(masses)} mass(es) x {len(selected_adducts)} adduct(s)...")
        try:
            results = self.search_engine.search_batch_masses(
                pairs, tolerance, self.get_selected_sources(),
                max_results_per_query=top_n)
            self.last_results = results
            self.last_search_params = {
                'type': 'mass', 'masses': masses, 'tolerance': tolerance,
                'adducts': [l for l, _, _ in selected_adducts], 'top_n': top_n}
            self.display_results(results)
            self.update_status(
                f"Found {len(results)} matches — "
                f"{len(masses)} mass(es) x {len(selected_adducts)} adduct(s), "
                f"top {top_n} each     Backend: {self.backend_label}")
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "Connection Error",
                f"Cannot reach server at {SERVER_URL}")
        except Exception as e:
            QMessageBox.critical(self, "Search Error", str(e))

    def perform_formula_search(self):
        text = self.formula_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Input Error", "Enter at least one formula.")
            return
        formulas = [f.strip() for f in re.split(r'[,\n]+', text) if f.strip()]
        top_n    = self.formula_top_n_spin.value()
        self.update_status(f"Searching {len(formulas)} formula(s)...")
        try:
            all_results = []
            for query_id, formula in enumerate(formulas):
                results = self.search_engine.search_by_formula(
                    formula, self.get_selected_sources(), max_results=top_n)
                for r in results:
                    r.update({'adduct': 'N/A', 'mass_error': None, 'ppm_error': None,
                              'neutral_mass': r.get('exact_mass'),
                              'query_id': query_id, 'query_mass': formula,
                              'query_adduct': ''})
                all_results.extend(results)
            self.last_results = all_results
            self.last_search_params = {
                'type': 'formula', 'formulas': formulas, 'top_n': top_n}
            self.display_results(all_results)
            self.update_status(
                f"Found {len(all_results)} matches — {len(formulas)} formula(s)     "
                f"Backend: {self.backend_label}")
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "Connection Error",
                f"Cannot reach server at {SERVER_URL}")
        except Exception as e:
            QMessageBox.critical(self, "Search Error", str(e))

    # ── Display ──────────────────────────────

    def build_source_url(self, source, source_id):
        template = SOURCE_URLS.get(source)
        if not template or not source_id:
            return ''
        return template.format(id=source_id)

    def display_results(self, results):
        self.results_table.setRowCount(0)
        self._all_results_rows = []
        if not results:
            self.export_button.setEnabled(False)
            self.copy_button.setEnabled(False)
            return

        grouped = {}
        for r in results:
            grouped.setdefault(r.get('query_id', 0), []).append(r)

        self.results_table.setRowCount(len(results) + len(grouped))
        current_row = 0

        for qid in sorted(grouped.keys()):
            grp        = grouped[qid]
            first      = grp[0]
            qmass      = first.get('query_mass', '')
            qlabel     = f"{qmass:.4f} Da" if isinstance(qmass, float) else str(qmass)
            qadduct    = first.get('query_adduct', first.get('adduct', ''))
            sep_text   = (f"Query {qid+1}: {qlabel} | {qadduct}  ({len(grp)} results)"
                          if qadduct else
                          f"Query {qid+1}: {qlabel}  ({len(grp)} results)")

            sep = QTableWidgetItem(sep_text)
            sep.setBackground(QColor(210, 210, 210))
            sep.setForeground(QColor(0, 0, 0))
            f = sep.font(); f.setBold(True); sep.setFont(f)
            self.results_table.setItem(current_row, 0, sep)
            self.results_table.setSpan(current_row, 0, 1, TOTAL_COLS)
            current_row += 1

            for r in grp:
                source    = r.get('source', '')
                source_id = r.get('source_id', '')
                url       = self.build_source_url(source, source_id)
                mass      = r.get('neutral_mass') or r.get('exact_mass', '')
                err_da    = r.get('mass_error')
                err_ppm   = r.get('ppm_error')
                inchikey  = r.get('inchikey', '')
                color     = SOURCE_COLORS.get(source, QColor(255, 255, 255))

                cells = [
                    (COL_NAME,     r.get('name', ''),                            False),
                    (COL_FORMULA,  r.get('formula', 'N/A'),                      False),
                    (COL_MASS,     str(mass) if mass != '' else '',               False),
                    (COL_ERR_DA,   str(err_da)  if err_da  is not None else '—', False),
                    (COL_ERR_PPM,  str(err_ppm) if err_ppm is not None else '—', False),
                    (COL_ADDUCT,   r.get('adduct', ''),                          False),
                    (COL_SOURCE,   source,                                        False),
                    (COL_URL,      url,                                           True),
                    (COL_INCHIKEY, inchikey,                                      False),
                ]
                for col, text, is_url in cells:
                    item = ClickableURLItem(text) if (is_url and text.startswith("http")) \
                           else QTableWidgetItem(text)
                    item.setBackground(color)
                    if not is_url:
                        item.setForeground(QColor(0, 0, 0))
                    self.results_table.setItem(current_row, col, item)

                self._all_results_rows.append((current_row, {
                    'name': r.get('name', ''), 'formula': r.get('formula', ''),
                    'source': source, 'inchikey': inchikey, 'source_id': source_id,
                }))
                current_row += 1

        self.export_button.setEnabled(True)
        self.copy_button.setEnabled(False)

    def on_selection_changed(self):
        self.copy_button.setEnabled(bool(self.results_table.selectedItems()))

    def on_cell_clicked(self, row, col):
        if col == COL_URL:
            item = self.results_table.item(row, col)
            if item and item.text().startswith("http"):
                QDesktopServices.openUrl(QUrl(item.text()))

    def copy_selected_row(self):
        row   = self.results_table.currentRow()
        cols  = self.results_table.columnCount()
        parts = [self.results_table.item(row, c).text()
                 for c in range(cols) if self.results_table.item(row, c)]
        QApplication.clipboard().setText('\t'.join(parts))
        self.update_status(f"Row {row+1} copied to clipboard")

    def export_to_csv(self):
        if not self.last_results:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "lucid_results.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                p = self.last_search_params
                if p.get('type') == 'mass':
                    writer.writerow([
                        f"# LUCID Mass Search — {len(p['masses'])} mass(es) x "
                        f"{len(p['adducts'])} adduct(s) | Tolerance: +/-{p['tolerance']} Da"])
                else:
                    writer.writerow([
                        f"# LUCID Formula Search — {len(p['formulas'])} formula(s)"])
                writer.writerow([])
                writer.writerow([
                    "Query", "Adduct", "Name", "Formula", "Exact Mass (Da)",
                    "Error (Da)", "Error (ppm)", "Source", "Source ID",
                    "Source URL", "InChIKey", "PubChem"
                ])
                for r in self.last_results:
                    source    = r.get('source', '')
                    source_id = r.get('source_id', '')
                    inchikey  = r.get('inchikey', '')
                    url       = self.build_source_url(source, source_id)
                    pubchem   = PUBCHEM_URL.format(inchikey=inchikey) if inchikey else ''
                    writer.writerow([
                        r.get('query_mass', ''),
                        r.get('adduct', r.get('query_adduct', '')),
                        r.get('name', ''), r.get('formula', ''),
                        r.get('neutral_mass') or r.get('exact_mass', ''),
                        r.get('mass_error', ''), r.get('ppm_error', ''),
                        source, source_id, url, inchikey, pubchem,
                    ])
            QMessageBox.information(self, "Export Successful", f"Saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def clear_search(self):
        self.mass_input.clear()
        self.tolerance_input.setText("0.5")
        self.formula_input.clear()
        self.results_table.setRowCount(0)
        self._all_results_rows  = []
        self.last_results       = []
        self.last_search_params = {}
        self.export_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.clear_filter()
        if self.db_loaded:
            parts = [f"{s}: {c:,}" for s, c in self.stats["by_source"].items()]
            self.update_status(
                f"Backend: {self.backend_label}     " + "     ".join(parts))

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