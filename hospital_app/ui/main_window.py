"""Navigable hospital dashboard and application workflow coordinator."""

import logging
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from hospital_app.database import Database
from hospital_app.models import DashboardStats, DoctorInput, PatientInput, QueueEntry
from hospital_app.repositories.appointment_repository import AppointmentRepository
from hospital_app.repositories.doctor_repository import DoctorRepository
from hospital_app.repositories.patient_repository import PatientRepository
from hospital_app.services.appointment_service import AppointmentService
from hospital_app.ui.appointment_form import AppointmentForm
from hospital_app.ui.dashboard_view import DashboardView
from hospital_app.ui.doctor_form import DoctorForm
from hospital_app.ui.history_view import HistoryView
from hospital_app.ui.patient_form import PatientForm
from hospital_app.ui.queue_view import QueueView


class MainWindow:
    NAV_ITEMS = (
        ("Dashboard", "dashboard"),
        ("Patient Management", "patients"),
        ("Doctor Management", "doctors"),
        ("Book Appointment", "booking"),
        ("Live Token Queue", "queue"),
        ("Appointment History", "history"),
    )

    def __init__(self, root: tk.Tk, database: Database) -> None:
        self.root = root
        self.patient_repository = PatientRepository(database)
        self.doctor_repository = DoctorRepository(database)
        self.appointment_repository = AppointmentRepository(database)
        self.service = AppointmentService(
            self.doctor_repository,
            self.patient_repository,
            self.appointment_repository,
        )
        self.current_page = "dashboard"
        self.pages: dict[str, ttk.Frame] = {}
        self.nav_buttons: dict[str, ttk.Button] = {}
        self.root.title("Hospital Outpatient Token & Appointment System")
        self.root.geometry("1440x880")
        self.root.minsize(1120, 720)
        self.root.report_callback_exception = self._report_callback_exception
        self._configure_styles()
        self._build_shell()
        self._build_pages()
        self._refresh_all()
        self.show_page("dashboard")

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("App.TFrame", background="#F3F6FA")
        style.configure("TFrame", background="#FFFFFF")
        style.configure("TLabelframe", background="#FFFFFF")
        style.configure(
            "TLabelframe.Label",
            background="#FFFFFF",
            foreground="#12304A",
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "Field.TLabel",
            background="#FFFFFF",
            foreground="#344054",
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "Info.TLabel",
            background="#FFFFFF",
            foreground="#526477",
            font=("Segoe UI", 9),
        )
        style.configure(
            "Accent.TButton",
            background="#087E6B",
            foreground="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            padding=(11, 7),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#066657"), ("disabled", "#AAB7C4")],
            foreground=[("disabled", "#F5F7FA")],
        )
        style.configure(
            "Nav.TButton",
            background="#12304A",
            foreground="#D5E4F0",
            font=("Segoe UI", 10),
            anchor="w",
            padding=(14, 11),
            borderwidth=0,
        )
        style.map(
            "Nav.TButton",
            background=[("active", "#1D4563"), ("selected", "#087E6B")],
            foreground=[("active", "#FFFFFF"), ("selected", "#FFFFFF")],
        )
        style.configure(
            "Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            foreground="#25364A",
            rowheight=29,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Treeview.Heading",
            background="#E7EDF3",
            foreground="#263B50",
            font=("Segoe UI", 9, "bold"),
            padding=7,
        )
        style.map("Treeview", background=[("selected", "#D7E9F5")])

    def _build_shell(self) -> None:
        self.root.configure(background="#F3F6FA")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        header = ttk.Frame(self.root, style="App.TFrame", padding=(20, 12))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            header,
            text="HOSPITAL OUTPATIENT CARE",
            font=("Segoe UI", 17, "bold"),
            foreground="#12304A",
        ).pack(side="left")
        ttk.Label(
            header,
            text="Token & Appointment Management",
            font=("Segoe UI", 10),
            foreground="#526477",
        ).pack(side="left", padx=(16, 0), pady=(4, 0))

        work_area = ttk.Frame(self.root)
        work_area.grid(row=1, column=0, sticky="nsew")
        work_area.columnconfigure(1, weight=1)
        work_area.rowconfigure(0, weight=1)
        sidebar = ttk.Frame(work_area, style="Sidebar.TFrame", padding=(10, 14))
        sidebar.grid(row=0, column=0, sticky="ns")
        ttk.Style(self.root).configure("Sidebar.TFrame", background="#12304A")
        ttk.Label(
            sidebar,
            text="NAVIGATION",
            background="#12304A",
            foreground="#91AFC4",
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", padx=12, pady=(2, 12))
        for label, key in self.NAV_ITEMS:
            button = ttk.Button(
                sidebar,
                text=label,
                style="Nav.TButton",
                command=lambda page=key: self.show_page(page),
            )
            button.pack(fill="x", pady=2)
            self.nav_buttons[key] = button

        self.content = ttk.Frame(work_area, style="App.TFrame")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            padding=(16, 7),
            background="#E7EDF3",
            foreground="#344054",
            font=("Segoe UI", 9),
        ).grid(row=2, column=0, sticky="ew")

    def _new_page(self, key: str) -> ttk.Frame:
        page = ttk.Frame(self.content, style="App.TFrame")
        page.grid(row=0, column=0, sticky="nsew")
        self.pages[key] = page
        return page

    def _build_pages(self) -> None:
        dashboard_page = self._new_page("dashboard")
        self.dashboard = DashboardView(
            dashboard_page,
            lambda: self.show_page("booking"),
            lambda: self.show_page("patients"),
            self._refresh_all,
        )
        self.dashboard.pack(fill="both", expand=True)

        patient_page = self._new_page("patients")
        self.patient_form = PatientForm(
            patient_page,
            self._register_patient,
            self._update_patient,
            self._delete_patient,
            self._search_patients,
            self._refresh_patient_page,
        )
        self.patient_form.pack(fill="both", expand=True)

        doctor_page = self._new_page("doctors")
        self.doctor_form = DoctorForm(
            doctor_page,
            self._create_doctor,
            self._update_doctor,
            self._delete_doctor,
            self._search_doctors,
            self._refresh_doctor_page,
        )
        self.doctor_form.pack(fill="both", expand=True)

        booking_page = self._new_page("booking")
        self.appointment_form = AppointmentForm(
            booking_page,
            self.patient_repository.get_all(),
            self.doctor_repository.get_all(),
            self._book_appointment,
            self._select_queue_doctor,
            lambda: self.show_page("history"),
        )
        self.appointment_form.pack(fill="both", expand=True, padx=18, pady=18)

        queue_page = self._new_page("queue")
        self.queue_view = QueueView(
            queue_page,
            self.doctor_repository.get_all(),
            self._call_next,
            self._mark_done,
            self._cancel_appointment,
            self._update_appointment_notes,
            self.refresh_queue,
            self._view_appointment_details,
        )
        self.queue_view.pack(fill="both", expand=True)

        history_page = self._new_page("history")
        self.history_view = HistoryView(
            history_page,
            self._search_history,
            self._update_appointment_notes,
            self._delete_appointment,
        )
        self.history_view.pack(fill="both", expand=True)

    def show_page(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            messagebox.showerror(
                "Page unavailable",
                f"The {key} page has not been configured.",
                parent=self.root,
            )
            return
        page.tkraise()
        self.current_page = key
        for name, button in self.nav_buttons.items():
            button.state(["selected"] if name == key else ["!selected"])
        if key == "dashboard":
            self._refresh_dashboard()
        elif key == "patients":
            self._refresh_patient_page()
        elif key == "doctors":
            self._refresh_doctor_page()
        elif key == "queue":
            self._refresh_queue()
        elif key == "history":
            self._search_history("", "", "")

    def _report_callback_exception(self, exception, value, traceback) -> None:
        logging.error(
            "Unexpected Tkinter callback failure",
            exc_info=(exception, value, traceback),
        )
        messagebox.showerror(
            "Unexpected application error",
            f"An unexpected error occurred:\n{value}",
            parent=self.root,
        )

    def _refresh_all(self) -> None:
        self._refresh_patient_page(self.patient_form.search_var.get())
        self._refresh_doctor_page(self.doctor_form.search_var.get())
        self._refresh_booking_choices()
        status = self.queue_view.status_var.get()
        self._refresh_queue(
            self.queue_view.doctor_id,
            self.queue_view.search_var.get(),
            None if status == self.queue_view.ALL_STATUSES else status,
        )
        self._search_history("", "", "")
        self._refresh_dashboard()

    def _refresh_patient_page(self, search: str = "") -> None:
        try:
            self.patient_form.show_patients(self.patient_repository.get_all(search))
        except sqlite3.Error as error:
            self._show_database_error("Could not load patients", error)

    def _refresh_doctor_page(self, search: str = "") -> None:
        try:
            self.doctor_form.show_doctors(self.doctor_repository.search(search))
        except sqlite3.Error as error:
            self._show_database_error("Could not load doctors", error)

    def _refresh_booking_choices(self) -> None:
        try:
            self.appointment_form.set_patients(self.patient_repository.get_all())
            self.appointment_form.set_doctors(self.doctor_repository.get_all())
            self.queue_view.set_doctors(self.doctor_repository.get_all())
        except sqlite3.Error as error:
            self._show_database_error("Could not refresh selection lists", error)

    def _register_patient(self, patient: PatientInput) -> None:
        try:
            patient_id = self.service.register_patient(patient)
        except ValueError as error:
            messagebox.showerror("Check patient details", str(error), parent=self.root)
            return
        except sqlite3.IntegrityError as error:
            messagebox.showerror(
                "Could not register patient",
                f"The record conflicts with an existing patient: {error}",
                parent=self.root,
            )
            return
        except sqlite3.Error as error:
            self._show_database_error("Could not register patient", error)
            return
        self.patient_form.clear()
        self._refresh_all()
        self.patient_form.select_patient(patient_id)
        self.appointment_form.select_patient(patient_id)
        self.status_var.set(f"Patient #{patient_id} registered successfully.")
        messagebox.showinfo(
            "Patient registered",
            f"Patient registered successfully. Patient ID: {patient_id}",
            parent=self.root,
        )

    def _update_patient(self, patient_id: int, patient: PatientInput) -> None:
        try:
            if not self.service.update_patient(patient_id, patient):
                raise ValueError("The selected patient no longer exists.")
        except ValueError as error:
            messagebox.showerror("Could not update patient", str(error), parent=self.root)
            return
        except sqlite3.IntegrityError as error:
            messagebox.showerror(
                "Could not update patient", f"Patient record conflict: {error}", parent=self.root
            )
            return
        except sqlite3.Error as error:
            self._show_database_error("Could not update patient", error)
            return
        self._refresh_all()
        self.status_var.set(f"Patient #{patient_id} updated.")
        messagebox.showinfo("Patient updated", "Patient details were updated.", parent=self.root)

    def _delete_patient(self, patient_id: int) -> None:
        if not messagebox.askyesno(
            "Delete patient",
            "Delete this patient? A patient with appointment records cannot be deleted.",
            parent=self.root,
        ):
            return
        try:
            deleted = self.patient_repository.delete(patient_id)
        except sqlite3.IntegrityError:
            messagebox.showwarning(
                "Patient has appointments",
                "This patient has appointment records and cannot be deleted.",
                parent=self.root,
            )
            return
        except sqlite3.Error as error:
            self._show_database_error("Could not delete patient", error)
            return
        if deleted:
            self.patient_form.clear()
            self._refresh_all()
            self.status_var.set(f"Patient #{patient_id} deleted.")

    def _search_patients(self, search: str) -> None:
        self._refresh_patient_page(search)

    def _create_doctor(self, doctor: DoctorInput) -> None:
        try:
            doctor_id = self.service.create_doctor(doctor)
        except ValueError as error:
            messagebox.showerror("Invalid doctor details", str(error), parent=self.root)
            return
        except sqlite3.IntegrityError as error:
            messagebox.showerror(
                "Doctor already exists", str(error), parent=self.root
            )
            return
        except sqlite3.Error as error:
            self._show_database_error("Could not add doctor", error)
            return
        self.doctor_form.clear()
        self._refresh_all()
        self.status_var.set(f"Doctor #{doctor_id} added.")
        messagebox.showinfo("Doctor added", f"Doctor ID: {doctor_id}", parent=self.root)

    def _update_doctor(self, doctor_id: int, doctor: DoctorInput) -> None:
        try:
            if not self.service.update_doctor(doctor_id, doctor):
                raise ValueError("The selected doctor no longer exists.")
        except ValueError as error:
            messagebox.showerror("Could not update doctor", str(error), parent=self.root)
            return
        except sqlite3.IntegrityError as error:
            messagebox.showerror("Doctor conflict", str(error), parent=self.root)
            return
        except sqlite3.Error as error:
            self._show_database_error("Could not update doctor", error)
            return
        self._refresh_all()
        self.status_var.set(f"Doctor #{doctor_id} updated.")

    def _delete_doctor(self, doctor_id: int) -> None:
        if not messagebox.askyesno(
            "Delete doctor",
            "Delete this doctor? A doctor with appointment records cannot be deleted.",
            parent=self.root,
        ):
            return
        try:
            deleted = self.service.delete_doctor(doctor_id)
        except sqlite3.IntegrityError:
            messagebox.showwarning(
                "Doctor has appointments",
                "This doctor has appointment records and cannot be deleted.",
                parent=self.root,
            )
            return
        except sqlite3.Error as error:
            self._show_database_error("Could not delete doctor", error)
            return
        if deleted:
            self.doctor_form.clear()
            self._refresh_all()
            self.status_var.set(f"Doctor #{doctor_id} deleted.")

    def _search_doctors(self, search: str) -> None:
        self._refresh_doctor_page(search)

    def _book_appointment(
        self,
        patient_id: int,
        doctor_id: int,
        appointment_date: str,
        appointment_time: str,
        notes: str,
    ) -> None:
        try:
            token = self.service.book_existing_patient(
                patient_id,
                doctor_id,
                appointment_date,
                appointment_time,
                notes,
            )
            appointment = self.appointment_repository.get_by_token(token)
        except ValueError as error:
            messagebox.showerror("Check appointment details", str(error), parent=self.root)
            return
        except sqlite3.IntegrityError as error:
            messagebox.showerror("Appointment conflict", str(error), parent=self.root)
            return
        except sqlite3.Error as error:
            self._show_database_error("Could not book appointment", error)
            return
        if appointment is None:
            messagebox.showerror(
                "Booking error",
                "The appointment was saved but could not be loaded for confirmation.",
                parent=self.root,
            )
            return
        self.appointment_form.clear_notes()
        self._refresh_all()
        self.show_page("queue")
        self.status_var.set(f"Appointment booked. Token #{token}.")
        messagebox.showinfo(
            "Appointment booked",
            f"Token number: {token}\n"
            f"Patient: {appointment.patient_name}\n"
            f"Doctor: {appointment.doctor_name} ({appointment.department})\n"
            f"Date: {appointment.appointment_date}\n"
            f"Time: {appointment.appointment_time}\n"
            "Status: Waiting",
            parent=self.root,
        )

    def _select_queue_doctor(self, doctor_id: int | None) -> None:
        self.queue_view.set_doctor_filter(doctor_id)

    def _refresh_queue(
        self,
        doctor_id: int | None = None,
        search: str = "",
        status: str | None = None,
    ) -> None:
        try:
            entries = self.service.get_queue(doctor_id, search, status)
        except sqlite3.Error as error:
            self._show_database_error("Could not load queue", error)
            return
        self.queue_view.doctor_id = doctor_id
        self.queue_view.show_entries(entries)

    def refresh_queue(
        self, doctor_id: int | None, search: str, status: str | None
    ) -> None:
        self._refresh_queue(doctor_id, search, status)

    def _call_next(self, doctor_id: int | None) -> None:
        try:
            token = self.service.call_next(doctor_id)
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror("Could not call next patient", str(error), parent=self.root)
            return
        self.status_var.set(
            f"Now calling token #{token}."
            if token is not None
            else "No waiting appointment is available for this queue."
        )
        self._refresh_all()

    def _mark_done(self, token: int) -> None:
        try:
            self.service.mark_done(token)
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror("Could not complete appointment", str(error), parent=self.root)
            return
        self.status_var.set(f"Token #{token} marked completed.")
        self._refresh_all()

    def _cancel_appointment(self, token: int) -> None:
        try:
            self.service.cancel_appointment(token)
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror("Could not cancel appointment", str(error), parent=self.root)
            return
        self.status_var.set(f"Token #{token} cancelled.")
        self._refresh_all()

    def _delete_appointment(self, token: int) -> None:
        if not messagebox.askyesno(
            "Delete appointment",
            f"Permanently delete appointment token #{token}?",
            parent=self.root,
        ):
            return
        try:
            if not self.appointment_repository.delete(token):
                raise ValueError("The selected appointment no longer exists.")
        except ValueError as error:
            messagebox.showerror("Could not delete appointment", str(error), parent=self.root)
            return
        except sqlite3.Error as error:
            self._show_database_error("Could not delete appointment", error)
            return
        self.status_var.set(f"Appointment token #{token} deleted.")
        self._refresh_all()

    def _update_appointment_notes(self, token: int, notes: str) -> None:
        if len(notes) > 500:
            messagebox.showerror(
                "Notes too long",
                "Appointment notes cannot exceed 500 characters.",
                parent=self.root,
            )
            return
        try:
            if not self.appointment_repository.update_notes(token, notes.strip()):
                raise ValueError("The selected appointment no longer exists.")
        except ValueError as error:
            messagebox.showerror("Could not update notes", str(error), parent=self.root)
            return
        except sqlite3.Error as error:
            self._show_database_error("Could not update notes", error)
            return
        self._refresh_all()
        self.status_var.set(f"Notes for token #{token} updated.")

    def _search_history(self, search: str, date: str, status: str) -> None:
        if date:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror(
                    "Invalid date", "Use YYYY-MM-DD for the date filter.", parent=self.root
                )
                return
        try:
            entries = self.appointment_repository.get_queue(
                search=search, status=status or None, appointment_date=date or None
            )
        except sqlite3.Error as error:
            self._show_database_error("Could not load appointment history", error)
            return
        self.history_view.show_entries(entries)

    def _view_appointment_details(self, appointment: QueueEntry) -> None:
        messagebox.showinfo(
            f"Appointment token #{appointment.token_no}",
            f"Patient: {appointment.patient_name}\n"
            f"Age / gender: {appointment.age} / {appointment.gender}\n"
            f"Doctor: {appointment.doctor_name}\n"
            f"Department: {appointment.department}\n"
            f"Room: {appointment.room_no}\n"
            f"Date / time: {appointment.appointment_date} "
            f"{appointment.appointment_time}\n"
            f"Status: {appointment.status}\n"
            f"Notes: {appointment.notes or 'None'}",
            parent=self.root,
        )

    def _refresh_dashboard(self) -> None:
        try:
            patient_count = len(self.patient_repository.get_all())
            doctors = self.doctor_repository.get_all()
            today, waiting, consulting, completed = (
                self.appointment_repository.get_dashboard_counts()
            )
            stats = DashboardStats(
                total_patients=patient_count,
                total_doctors=len(doctors),
                todays_appointments=today,
                waiting_patients=waiting,
                in_consultation=consulting,
                completed_consultations=completed,
            )
            appointments = self.appointment_repository.get_upcoming_appointments()
            recent_patients = self.patient_repository.get_recent()
        except sqlite3.Error as error:
            self._show_database_error("Could not refresh dashboard", error)
            return
        self.dashboard.update_dashboard(stats, appointments, recent_patients)

    def _show_database_error(self, title: str, error: sqlite3.Error) -> None:
        logging.exception("%s: %s", title, error)
        messagebox.showerror(title, f"{error}", parent=self.root)
