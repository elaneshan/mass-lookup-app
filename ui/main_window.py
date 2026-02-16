"""
Mass Lookup Tool - Main GUI Window v2
======================================

Enhanced desktop application with:
- Mass search with ion mode selection
- Formula search
- Multi-source database display
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
    QComboBox, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from search.search_engine import SearchEngine


class MassLookupWindow(QMainWindow):
    """Main application window for mass lookup tool."""

    def __init__(self):
        super().__init__()

        # Initialize search engine
        try:
            self.search_engine = SearchEngine()
            stats = self.search_engine.get_stats()
            self.db_loaded = True
            self.stats = stats
        except FileNotFoundError as e:
            self.db_loaded = False
            self.stats = {}
            QMessageBox.critical(
                self,
                "Database Error",
                f"Could not load database:\n{str(e)}"
            )

        # Store last search results for export
        self.last_results = []
        self.last_search_params = {}

        # Setup UI
        self.init_ui()

        # Show database stats if loaded
        if self.db_loaded:
            source_info = ", ".join([f"{src}: {count:,}" for src, count in self.stats['by_source'].items()])
            self.update_status(f"Database loaded - {source_info}")

    def init_ui(self):
        """Initialize the user interface."""

        # Window properties
        self.setWindowTitle("LC-MS Mass Lookup Tool v2")
        self.setGeometry(100, 100, 1200, 750)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Add components
        main_layout.addWidget(self.create_search_panel())
        main_layout.addWidget(self.create_results_panel())
        main_layout.addWidget(self.create_status_bar())

    def create_search_panel(self):
        """Create the enhanced search input panel."""

        group = QGroupBox("Search Parameters")
        layout = QVBoxLayout()

        # Search mode selection
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Search Mode:"))

        self.mode_button_group = QButtonGroup()
        self.mass_mode_radio = QRadioButton("Mass")
        self.formula_mode_radio = QRadioButton("Formula")
        self.mass_mode_radio.setChecked(True)

        self.mode_button_group.addButton(self.mass_mode_radio)
        self.mode_button_group.addButton(self.formula_mode_radio)

        # Connect to update UI when mode changes
        self.mass_mode_radio.toggled.connect(self.on_mode_changed)

        mode_row.addWidget(self.mass_mode_radio)
        mode_row.addWidget(self.formula_mode_radio)
        mode_row.addStretch()

        layout.addLayout(mode_row)

        # Search input row (changes based on mode)
        input_row = QHBoxLayout()

        # Mass input (shown when mass mode selected)
        self.mass_label = QLabel("Target Mass (Da):")
        input_row.addWidget(self.mass_label)

        self.mass_input = QLineEdit()
        self.mass_input.setPlaceholderText("e.g., 181.071 (observed mass)")
        self.mass_input.returnPressed.connect(self.perform_search)
        input_row.addWidget(self.mass_input)

        # Tolerance (only for mass mode)
        self.tolerance_label = QLabel("Tolerance (±):")
        input_row.addWidget(self.tolerance_label)

        self.tolerance_input = QLineEdit()
        self.tolerance_input.setText("0.5")
        self.tolerance_input.setMaximumWidth(100)
        self.tolerance_input.returnPressed.connect(self.perform_search)
        input_row.addWidget(self.tolerance_input)

        self.tolerance_unit_label = QLabel("Da")
        input_row.addWidget(self.tolerance_unit_label)

        # Formula input (shown when formula mode selected)
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

        # Ion mode row (only for mass searches)
        ion_row = QHBoxLayout()

        self.ion_mode_label = QLabel("Ion Mode:")
        ion_row.addWidget(self.ion_mode_label)

        self.ion_mode_combo = QComboBox()
        self.ion_mode_combo.addItems(["Neutral (exact mass)", "Positive [M+H]+", "Negative [M-H]-"])
        self.ion_mode_combo.setMaximumWidth(200)
        ion_row.addWidget(self.ion_mode_combo)

        ion_row.addStretch()

        layout.addLayout(ion_row)

        # Button row
        button_row = QHBoxLayout()

        self.search_button = QPushButton("Search")
        self.search_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 8px; font-weight: bold; }")
        self.search_button.clicked.connect(self.perform_search)
        button_row.addWidget(self.search_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_search)
        button_row.addWidget(self.clear_button)

        self.export_button = QPushButton("Export to CSV")
        self.export_button.clicked.connect(self.export_to_csv)
        self.export_button.setEnabled(False)  # Disabled until results exist
        button_row.addWidget(self.export_button)

        button_row.addStretch()

        layout.addLayout(button_row)

        group.setLayout(layout)
        return group

    def create_results_panel(self):
        """Create the results table panel."""

        group = QGroupBox("Results")
        layout = QVBoxLayout()

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels([
            "Name", "Formula", "Exact Mass (Da)", "Error (Da)", "Error (ppm)", "Source", "Source ID"
        ])

        # Table properties
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Column widths
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Formula
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Mass
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Error Da
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Error ppm
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Source
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # ID

        layout.addWidget(self.results_table)

        group.setLayout(layout)
        return group

    def create_status_bar(self):
        """Create status bar."""

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("QLabel { padding: 5px; }")
        return self.status_label

    def on_mode_changed(self):
        """Handle search mode change."""

        is_mass_mode = self.mass_mode_radio.isChecked()

        # Show/hide appropriate inputs
        self.mass_label.setVisible(is_mass_mode)
        self.mass_input.setVisible(is_mass_mode)
        self.tolerance_label.setVisible(is_mass_mode)
        self.tolerance_input.setVisible(is_mass_mode)
        self.tolerance_unit_label.setVisible(is_mass_mode)
        self.ion_mode_label.setVisible(is_mass_mode)
        self.ion_mode_combo.setVisible(is_mass_mode)

        self.formula_label.setVisible(not is_mass_mode)
        self.formula_input.setVisible(not is_mass_mode)

        # Focus appropriate input
        if is_mass_mode:
            self.mass_input.setFocus()
        else:
            self.formula_input.setFocus()

    def perform_search(self):
        """Execute the search based on selected mode."""

        if not self.db_loaded:
            QMessageBox.warning(self, "Database Error", "Database is not loaded.")
            return

        # Determine search mode
        if self.mass_mode_radio.isChecked():
            self.perform_mass_search()
        else:
            self.perform_formula_search()

    def perform_mass_search(self):
        """Execute mass search with ion mode."""

        # Get inputs
        mass_text = self.mass_input.text().strip()
        tolerance_text = self.tolerance_input.text().strip()

        # Validate
        if not mass_text:
            QMessageBox.warning(self, "Input Error", "Please enter a target mass.")
            self.mass_input.setFocus()
            return

        try:
            target_mass = float(mass_text)
        except ValueError:
            QMessageBox.warning(self, "Input Error", f"Invalid mass value: '{mass_text}'")
            self.mass_input.setFocus()
            return

        try:
            tolerance = float(tolerance_text) if tolerance_text else 0.5
        except ValueError:
            QMessageBox.warning(self, "Input Error", f"Invalid tolerance: '{tolerance_text}'")
            return

        # Get ion mode
        ion_mode_map = {
            0: 'neutral',
            1: 'positive',
            2: 'negative'
        }
        ion_mode = ion_mode_map[self.ion_mode_combo.currentIndex()]

        # Perform search
        self.update_status(f"Searching for mass {target_mass} ± {tolerance} Da ({ion_mode} mode)...")

        try:
            results = self.search_engine.search_by_mass(target_mass, tolerance, ion_mode)
            self.last_results = results
            self.last_search_params = {
                'type': 'mass',
                'mass': target_mass,
                'tolerance': tolerance,
                'ion_mode': ion_mode
            }
            self.display_mass_results(results, target_mass, tolerance, ion_mode)
        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Error: {str(e)}")
            self.update_status("Search failed")

    def perform_formula_search(self):
        """Execute formula search."""

        # Get input
        formula = self.formula_input.text().strip()

        if not formula:
            QMessageBox.warning(self, "Input Error", "Please enter a molecular formula.")
            self.formula_input.setFocus()
            return

        # Perform search
        self.update_status(f"Searching for formula: {formula}...")

        try:
            results = self.search_engine.search_by_formula(formula)
            self.last_results = results
            self.last_search_params = {
                'type': 'formula',
                'formula': formula
            }
            self.display_formula_results(results, formula)
        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Error: {str(e)}")
            self.update_status("Search failed")

    def display_mass_results(self, results, target_mass, tolerance, ion_mode):
        """Display mass search results."""

        self.results_table.setRowCount(0)

        if not results:
            self.update_status(f"No matches found for {target_mass} ± {tolerance} Da ({ion_mode})")
            self.export_button.setEnabled(False)
            return

        self.results_table.setRowCount(len(results))

        for row_idx, result in enumerate(results):
            # Name
            self.results_table.setItem(row_idx, 0, QTableWidgetItem(result['name']))

            # Formula
            self.results_table.setItem(row_idx, 1, QTableWidgetItem(result['formula']))

            # Exact Mass (neutral)
            self.results_table.setItem(row_idx, 2, QTableWidgetItem(str(result['neutral_mass'])))

            # Error (Da)
            error_item = QTableWidgetItem(str(result['mass_error']))
            error_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.results_table.setItem(row_idx, 3, error_item)

            # Error (ppm)
            ppm_item = QTableWidgetItem(str(result['ppm_error']))
            ppm_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.results_table.setItem(row_idx, 4, ppm_item)

            # Source
            self.results_table.setItem(row_idx, 5, QTableWidgetItem(result['source']))

            # Source ID
            self.results_table.setItem(row_idx, 6, QTableWidgetItem(result['source_id']))

        self.update_status(f"Found {len(results):,} matches for {target_mass} ± {tolerance} Da ({ion_mode})")
        self.export_button.setEnabled(True)

    def display_formula_results(self, results, formula):
        """Display formula search results."""

        self.results_table.setRowCount(0)

        if not results:
            self.update_status(f"No matches found for formula: {formula}")
            self.export_button.setEnabled(False)
            return

        self.results_table.setRowCount(len(results))

        for row_idx, result in enumerate(results):
            # Name
            self.results_table.setItem(row_idx, 0, QTableWidgetItem(result['name']))

            # Formula
            self.results_table.setItem(row_idx, 1, QTableWidgetItem(result['formula']))

            # Exact Mass
            self.results_table.setItem(row_idx, 2, QTableWidgetItem(str(result['exact_mass'])))

            # Error columns - leave empty for formula search
            self.results_table.setItem(row_idx, 3, QTableWidgetItem("—"))
            self.results_table.setItem(row_idx, 4, QTableWidgetItem("—"))

            # Source
            self.results_table.setItem(row_idx, 5, QTableWidgetItem(result['source']))

            # Source ID
            self.results_table.setItem(row_idx, 6, QTableWidgetItem(result['source_id']))

        self.update_status(f"Found {len(results):,} matches for formula: {formula}")
        self.export_button.setEnabled(True)

    def export_to_csv(self):
        """Export current results to CSV file."""

        if not self.last_results:
            QMessageBox.warning(self, "Export Error", "No results to export.")
            return

        # Get save file path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Results to CSV",
            "mass_lookup_results.csv",
            "CSV Files (*.csv)"
        )

        if not file_path:
            return  # User cancelled

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Write header with search parameters
                search_type = self.last_search_params.get('type', 'unknown')
                if search_type == 'mass':
                    writer.writerow([f"# Mass Search: {self.last_search_params['mass']} ± {self.last_search_params['tolerance']} Da ({self.last_search_params['ion_mode']} mode)"])
                else:
                    writer.writerow([f"# Formula Search: {self.last_search_params['formula']}"])

                writer.writerow([])  # Blank line

                # Column headers
                if search_type == 'mass':
                    writer.writerow(['Name', 'Formula', 'Neutral Mass (Da)', 'Mass Error (Da)', 'PPM Error', 'Source Database', 'Source ID'])

                    # Data rows
                    for result in self.last_results:
                        writer.writerow([
                            result['name'],
                            result['formula'],
                            result['neutral_mass'],
                            result['mass_error'],
                            result['ppm_error'],
                            result['source'],
                            result['source_id']
                        ])
                else:
                    writer.writerow(['Name', 'Formula', 'Exact Mass (Da)', 'Source Database', 'Source ID'])

                    # Data rows
                    for result in self.last_results:
                        writer.writerow([
                            result['name'],
                            result['formula'],
                            result['exact_mass'],
                            result['source'],
                            result['source_id']
                        ])

            QMessageBox.information(
                self,
                "Export Successful",
                f"Results exported to:\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export results:\n{str(e)}"
            )

    def clear_search(self):
        """Clear search inputs and results."""

        self.mass_input.clear()
        self.tolerance_input.setText("0.5")
        self.formula_input.clear()
        self.results_table.setRowCount(0)
        self.last_results = []
        self.last_search_params = {}
        self.export_button.setEnabled(False)

        if self.db_loaded:
            source_info = ", ".join([f"{src}: {count:,}" for src, count in self.stats['by_source'].items()])
            self.update_status(f"Database loaded - {source_info}")

        # Focus appropriate input
        if self.mass_mode_radio.isChecked():
            self.mass_input.setFocus()
        else:
            self.formula_input.setFocus()

    def update_status(self, message):
        """Update status bar message."""
        self.status_label.setText(message)


def main():
    """Main application entry point."""

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = MassLookupWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()