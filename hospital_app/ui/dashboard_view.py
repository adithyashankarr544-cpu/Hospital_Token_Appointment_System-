"""Dashboard cards and today's appointment overview."""

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from hospital_app.models import DashboardStats, Patient, QueueEntry


class DashboardView(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        on_book: Callable[[], None],
        on_register: Callable[[], None],
        on_refresh: Callable[[], None],
    ) -> None:
        super().__init__(parent, padding=18)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        ttk.Label(
            self, text="Hospital Dashboard", font=("Segoe UI", 19, "bold")
        ).grid(row=0, column=0, sticky="w")
        cards = ttk.Frame(self)
        cards.grid(row=1, column=0, sticky="ew", pady=(14, 14))
        self.card_vars: dict[str, tk.StringVar] = {}
        labels = (
            ("patients", "Registered patients"),
            ("doctors", "Available doctors"),
            ("today", "Today's appointments"),
            ("waiting", "Waiting patients"),
            ("consultation", "In consultation"),
            ("completed", "Completed"),
        )
        for column, (key, title) in enumerate(labels):
            cards.columnconfigure(column, weight=1)
            card = ttk.LabelFrame(cards, text=title, padding=(12, 8))
            card.grid(row=0, column=column, sticky="ew", padx=(0, 8))
            value = tk.StringVar(value="0")
            self.card_vars[key] = value
            ttk.Label(
                card,
                textvariable=value,
                font=("Segoe UI", 20, "bold"),
                foreground="#087E6B",
            ).pack(anchor="w")

        body = ttk.Frame(self)
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        today = ttk.LabelFrame(
            body, text="Today's & upcoming appointments", padding=12
        )
        today.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        today.columnconfigure(0, weight=1)
        today.rowconfigure(0, weight=1)
        columns = ("token", "patient", "doctor", "time", "status")
        self.appointments_tree = ttk.Treeview(today, columns=columns, show="headings")
        for key, title, width in (
            ("token", "Token", 65),
            ("patient", "Patient", 150),
            ("doctor", "Doctor", 145),
            ("time", "Time", 90),
            ("status", "Status", 125),
        ):
            self.appointments_tree.heading(key, text=title)
            self.appointments_tree.column(key, width=width, minwidth=55, anchor="w")
        self.appointments_tree.grid(row=0, column=0, sticky="nsew")
        today_scroll = ttk.Scrollbar(
            today, orient="vertical", command=self.appointments_tree.yview
        )
        today_scroll.grid(row=0, column=1, sticky="ns")
        self.appointments_tree.configure(yscrollcommand=today_scroll.set)

        recent = ttk.LabelFrame(body, text="Recent patient registrations", padding=12)
        recent.grid(row=0, column=1, sticky="nsew")
        recent.columnconfigure(0, weight=1)
        recent.rowconfigure(0, weight=1)
        self.patients_tree = ttk.Treeview(
            recent, columns=("name", "phone"), show="headings"
        )
        self.patients_tree.heading("name", text="Patient")
        self.patients_tree.heading("phone", text="Phone")
        self.patients_tree.column("name", width=165, minwidth=80)
        self.patients_tree.column("phone", width=120, minwidth=80)
        self.patients_tree.grid(row=0, column=0, sticky="nsew")
        recent_scroll = ttk.Scrollbar(
            recent, orient="vertical", command=self.patients_tree.yview
        )
        recent_scroll.grid(row=0, column=1, sticky="ns")
        self.patients_tree.configure(yscrollcommand=recent_scroll.set)
        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        ttk.Button(
            actions,
            text="Quick Register Patient",
            command=on_register,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="Quick Book Appointment",
            style="Accent.TButton",
            command=on_book,
        ).pack(side="left", padx=8)
        ttk.Button(actions, text="Refresh Dashboard", command=on_refresh).pack(
            side="right"
        )

    def update_dashboard(
        self,
        stats: DashboardStats,
        appointments: list[QueueEntry],
        patients: list[Patient],
    ) -> None:
        values = {
            "patients": stats.total_patients,
            "doctors": stats.total_doctors,
            "today": stats.todays_appointments,
            "waiting": stats.waiting_patients,
            "consultation": stats.in_consultation,
            "completed": stats.completed_consultations,
        }
        for key, value in values.items():
            self.card_vars[key].set(str(value))
        for tree in (self.appointments_tree, self.patients_tree):
            for item in tree.get_children():
                tree.delete(item)
        for appointment in appointments:
            self.appointments_tree.insert(
                "",
                "end",
                values=(
                    appointment.token_no,
                    appointment.patient_name,
                    appointment.doctor_name,
                    appointment.appointment_time,
                    appointment.status,
                ),
            )
        for patient in patients:
            self.patients_tree.insert(
                "", "end", values=(patient.name, patient.phone)
            )
