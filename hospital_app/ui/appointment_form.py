"""Appointment booking form for selecting registered patients and doctors."""

import tkinter as tk
from collections.abc import Callable
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

from hospital_app.models import Doctor, Patient


class AppointmentForm(ttk.LabelFrame):
    def __init__(
        self,
        parent: tk.Misc,
        patients: list[Patient],
        doctors: list[Doctor],
        on_book: Callable[[int, int, str, str, str], None],
        on_doctor_change: Callable[[int | None], None],
        on_view_appointments: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, text="  Book Appointment  ", padding=16)
        self.on_book = on_book
        self.on_doctor_change = on_doctor_change
        self.on_view_appointments = on_view_appointments
        self.patient_var = tk.StringVar()
        self.doctor_var = tk.StringVar()
        self.doctor_info_var = tk.StringVar(value="Select a doctor for details.")
        initial_time = datetime.now().replace(second=0, microsecond=0) + timedelta(
            minutes=1
        )
        self.date_var = tk.StringVar(value=initial_time.strftime("%Y-%m-%d"))
        self.time_var = tk.StringVar(value=initial_time.strftime("%H:%M"))
        self.patient_by_display: dict[str, Patient] = {}
        self.doctor_by_display = {doctor.display_name: doctor for doctor in doctors}
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Patient", style="Field.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=8
        )
        self.patient_combo = ttk.Combobox(
            self, textvariable=self.patient_var, state="readonly"
        )
        self.patient_combo.grid(row=0, column=1, sticky="ew", pady=8)
        ttk.Label(self, text="Doctor", style="Field.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 12), pady=8
        )
        self.doctor_combo = ttk.Combobox(
            self,
            textvariable=self.doctor_var,
            values=tuple(self.doctor_by_display),
            state="readonly",
        )
        self.doctor_combo.grid(row=1, column=1, sticky="ew", pady=8)
        self.doctor_combo.bind("<<ComboboxSelected>>", self._doctor_selected)
        ttk.Label(self, text="Department / fee / room", style="Field.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=8
        )
        ttk.Label(
            self,
            textvariable=self.doctor_info_var,
            style="Info.TLabel",
            wraplength=310,
        ).grid(row=2, column=1, sticky="w", pady=8)
        ttk.Label(self, text="Appointment date (YYYY-MM-DD)", style="Field.TLabel").grid(
            row=3, column=0, sticky="w", padx=(0, 12), pady=8
        )
        ttk.Entry(self, textvariable=self.date_var).grid(
            row=3, column=1, sticky="ew", pady=8
        )
        ttk.Label(self, text="Appointment time (HH:MM)", style="Field.TLabel").grid(
            row=4, column=0, sticky="w", padx=(0, 12), pady=8
        )
        ttk.Entry(self, textvariable=self.time_var).grid(
            row=4, column=1, sticky="ew", pady=8
        )
        ttk.Label(self, text="Appointment notes", style="Field.TLabel").grid(
            row=5, column=0, sticky="nw", padx=(0, 12), pady=8
        )
        self.notes_text = tk.Text(self, height=6, wrap="word", font=("Segoe UI", 10))
        self.notes_text.grid(row=5, column=1, sticky="ew", pady=8)
        actions = ttk.Frame(self)
        actions.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(
            actions,
            text="GENERATE TOKEN & BOOK APPOINTMENT",
            style="Accent.TButton",
            command=self._book,
        ).grid(row=0, column=0, sticky="ew", ipady=7)
        ttk.Button(
            actions, text="Clear Form", command=self.clear
        ).grid(row=1, column=0, sticky="ew", pady=(6, 0))
        if self.on_view_appointments is not None:
            ttk.Button(
                actions, text="View Appointments", command=self.on_view_appointments
            ).grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.set_patients(patients)

    def set_patients(self, patients: list[Patient]) -> None:
        selected_id = self.selected_patient_id
        self.patient_by_display = {
            f"{patient.name} | {patient.phone}": patient for patient in patients
        }
        self.patient_combo.configure(values=tuple(self.patient_by_display))
        selected = next(
            (
                display
                for display, patient in self.patient_by_display.items()
                if patient.patient_id == selected_id
            ),
            "",
        )
        self.patient_var.set(selected)

    def set_doctors(self, doctors: list[Doctor]) -> None:
        selected_id = self.get_selected_doctor_id()
        self.doctor_by_display = {doctor.display_name: doctor for doctor in doctors}
        self.doctor_combo.configure(values=tuple(self.doctor_by_display))
        selected = next(
            (
                display
                for display, doctor in self.doctor_by_display.items()
                if doctor.doctor_id == selected_id
            ),
            "",
        )
        self.doctor_var.set(selected)
        doctor = self.doctor_by_display.get(selected)
        if doctor is not None:
            self.doctor_info_var.set(
                f"{doctor.dept}  |  Rs. {doctor.fee:,.2f}  |  Room {doctor.room_no}"
            )
        else:
            self.doctor_info_var.set("Select a doctor for details.")

    @property
    def selected_patient_id(self) -> int | None:
        patient = self.patient_by_display.get(self.patient_var.get())
        return patient.patient_id if patient else None

    def select_patient(self, patient_id: int) -> None:
        for display, patient in self.patient_by_display.items():
            if patient.patient_id == patient_id:
                self.patient_var.set(display)
                return

    def get_selected_doctor_id(self) -> int | None:
        doctor = self.doctor_by_display.get(self.doctor_var.get())
        return doctor.doctor_id if doctor else None

    def _doctor_selected(self, _event: tk.Event) -> None:
        doctor = self.doctor_by_display.get(self.doctor_var.get())
        if doctor is None:
            self.doctor_info_var.set("Select a doctor for details.")
            self.on_doctor_change(None)
            return
        self.doctor_info_var.set(
            f"{doctor.dept}  |  Rs. {doctor.fee:,.2f}  |  Room {doctor.room_no}"
        )
        self.on_doctor_change(doctor.doctor_id)

    def _book(self) -> None:
        patient_id = self.selected_patient_id
        doctor_id = self.get_selected_doctor_id()
        if patient_id is None:
            messagebox.showwarning(
                "Patient required", "Select a registered patient first.", parent=self
            )
            return
        if doctor_id is None:
            messagebox.showwarning(
                "Doctor required", "Select a doctor first.", parent=self
            )
            return
        self.on_book(
            patient_id,
            doctor_id,
            self.date_var.get(),
            self.time_var.get(),
            self.notes_text.get("1.0", "end-1c"),
        )

    def clear_notes(self) -> None:
        self.notes_text.delete("1.0", tk.END)

    def clear(self) -> None:
        initial_time = datetime.now().replace(second=0, microsecond=0) + timedelta(
            minutes=1
        )
        self.patient_var.set("")
        self.doctor_var.set("")
        self.date_var.set(initial_time.strftime("%Y-%m-%d"))
        self.time_var.set(initial_time.strftime("%H:%M"))
        self.doctor_info_var.set("Select a doctor for details.")
        self.on_doctor_change(None)
        self.notes_text.delete("1.0", tk.END)
