# -*- coding: utf-8 -*-
import os
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog

# Caricamento dinamico del file .ui
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), 'settings_dialog.ui')
)


class SettingsDialog(QDialog, FORM_CLASS):
    def __init__(self, step_h=0.2, max_iterations=3000, max_radius_m=400.0, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setupUi(self)

        # Inizializza i valori nelle SpinBox del file .ui
        self.step_h_box.setValue(step_h)
        self.max_iter_box.setValue(max_iterations)

        if hasattr(self, 'max_radius_box'):
            self.max_radius_box.setValue(max_radius_m)

    def get_values(self):
        """Restituisce le impostazioni correnti."""
        max_rad = self.max_radius_box.value() if hasattr(self, 'max_radius_box') else 400.0
        return self.step_h_box.value(), self.max_iter_box.value(), max_rad