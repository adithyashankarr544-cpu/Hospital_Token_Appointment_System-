"""Live token queue with doctor/status filters and appointment actions."""

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from hospital_app.models import Doctor, QueueEntry


class QueueView(ttk.Frame):
    ALL_DOCTORS = "All doctors"
    ALL_STATUSES = "All statuses"

    def __init__(
        self,
        parent: tk.Misc,
        doctors: list[Doctor],
        on_call_next: Callable[[int | None], None],
        on_mark_done: Callable[[int], None],
        on_cancel: Callable[[int], None],
        on_update_notes: Callable[[int, str], None],
        on_refresh: Callable[[int | None, str, str | None], None],
        on_view_details: Callable[[QueueEntry], None],
    ) -> None:
        super().__init__(parent, padding=16)
        self.on_call_next = on_call_next
        self.on_mark_done = on_mark_done
        self.on_cancel = on_cancel
        self.on_update_notes = on_update_notes
        self.on_refresh = on_refresh
        self.on_view_details = on_view_details
        self.doctor_id: int | None = None
        self.entries_by_token: dict[int, QueueEntry] = {}
        self.doctor_by_display = {doctor.display_name: doctor for doctor in doctors}
        self.filter_var = tk.StringVar(value=self.ALL_DOCTORS)
        self.status_var = tk.StringVar(value=self.ALL_STATUSES)
        self.search_var = tk.StringVar()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.LabelFrame(self, text="Queue filters", padding=10)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.columnconfigure(2, weight=1)
        self.doctor_combo = ttk.Combobox(
            toolbar,
            textvariable=self.filter_var,
            values=(self.ALL_DOCTORS, *self.doctor_by_display),
            state="readonly",
            width=25,
        )
        self.doctor_combo.grid(row=0, column=0, padx=(0, 8))
        self.doctor_combo.bind("<<ComboboxSelected>>", self._filter_changed)
        self.status_combo = ttk.Combobox(
            toolbar,
            textvariable=self.status_var,
            values=(self.ALL_STATUSES, "Waiting", "In Consultation", "Completed", "Cancelled"),
            state="readonly",
            width=19,
        )
        self.status_combo.grid(row=0, column=1, padx=(0, 8))
        self.status_combo.bind("<<ComboboxSelected>>", self._refresh)
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=2, sticky="ew", padx=(0, 8))
        self.search_entry.bind("<Return>", self._search)
        ttk.Button(toolbar, text="Search", command=self._search).grid(
            row=0, column=3, padx=(0, 7)
        )
        ttk.Button(toolbar, text="Refresh Queue", command=self._refresh).grid(
            row=0, column=4
        )

        actions = ttk.Frame(self)
        actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(
            actions,
            text="CALL NEXT",
            style="Accent.TButton",
            command=self._call_next,
        ).pack(side="left", padx=(0, 7))
        self.done_button = ttk.Button(
            actions, text="MARK DONE", command=self._mark_done, state="disabled"
        )
        self.done_button.pack(side="left", padx=7)
        self.cancel_button = ttk.Button(
            actions,
            text="CANCEL APPOINTMENT",
            command=self._cancel,
            state="disabled",
        )
        self.cancel_button.pack(side="left", padx=7)
        ttk.Button(
            actions, text="VIEW DETAILS", command=self._details
        ).pack(side="left", padx=7)
        self.summary_var = tk.StringVar(value="Queue is ready.")
        ttk.Label(actions, textvariable=self.summary_var, style="Info.TLabel").pack(
            side="right"
        )

        table = ttk.LabelFrame(self, text="Live token queue", padding=10)
        table.grid(row=1, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        columns = (
            "token",
            "patient",
            "age",
            "gender",
            "doctor",
            "department",
            "date",
            "time",
            "status",
        )
        self.tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse")
        headings = {
            "token": "Token",
            "patient": "Patient name",
            "age": "Age",
            "gender": "Gender",
            "doctor": "Doctor",
            "department": "Department",
            "date": "Appointment date",
            "time": "Appointment time",
            "status": "Status",
        }
        widths = {
            "token": 70,
            "patient": 150,
            "age": 48,
            "gender": 75,
            "doctor": 125,
            "department": 140,
            "date": 112,
            "time": 95,
            "status": 125,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                minwidth=50,
                anchor="center" if column in {"token", "age", "gender"} else "w",
            )
        for status, color in (
            ("Waiting", "#9A6700"),
            ("In Consultation", "#166534"),
            ("Completed", "#667085"),
            ("Cancelled", "#B42318"),
        ):
            self.tree.tag_configure(status, foreground=color)
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self._selection_changed()

    def _selected_token(self) -> int | None:
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def _selected_entry(self) -> QueueEntry | None:
        token = self._selected_token()
        return self.entries_by_token.get(token) if token is not None else None

    def _filter_changed(self, _event: tk.Event) -> None:
        doctor = self.doctor_by_display.get(self.filter_var.get())
        self.doctor_id = doctor.doctor_id if doctor else None
        self._refresh()

    def set_doctor_filter(self, doctor_id: int | None) -> None:
        self.doctor_id = doctor_id
        self.filter_var.set(
            next(
                (
                    display
                    for display, doctor in self.doctor_by_display.items()
                    if doctor.doctor_id == doctor_id
                ),
                self.ALL_DOCTORS,
            )
        )

    def set_doctors(self, doctors: list[Doctor]) -> None:
        self.doctor_by_display = {doctor.display_name: doctor for doctor in doctors}
        self.doctor_combo.configure(values=(self.ALL_DOCTORS, *self.doctor_by_display))
        if self.doctor_id is not None and not any(
            doctor.doctor_id == self.doctor_id
            for doctor in self.doctor_by_display.values()
        ):
            self.doctor_id = None
        self.set_doctor_filter(self.doctor_id)

    def _search(self, _event: tk.Event | None = None) -> None:
        self._refresh()

    def _refresh(self, _event: tk.Event | None = None) -> None:
        status = self.status_var.get()
        self.on_refresh(
            self.doctor_id,
            self.search_var.get().strip(),
            None if status == self.ALL_STATUSES else status,
        )

    def _call_next(self) -> None:
        self.on_call_next(self.doctor_id)

    def _mark_done(self) -> None:
        token = self._selected_token()
        if token is not None:
            self.on_mark_done(token)

    def _cancel(self) -> None:
        token = self._selected_token()
        if token is not None and messagebox.askyesno(
            "Cancel appointment",
            f"Cancel waiting appointment token {token}?",
            parent=self,
        ):
            self.on_cancel(token)

    def _details(self) -> None:
        entry = self._selected_entry()
        if entry is not None:
            self.on_view_details(entry)

    def show_entries(self, entries: list[QueueEntry]) -> None:
        selected_token = self._selected_token()
        self.entries_by_token = {entry.token_no: entry for entry in entries}
        for item in self.tree.get_children():
            self.tree.delete(item)
        for entry in entries:
            self.tree.insert(
                "",
                "end",
                iid=str(entry.token_no),
                values=(
                    entry.token_no,
                    entry.patient_name,
                    entry.age,
                    entry.gender,
                    entry.doctor_name,
                    entry.department,
                    entry.appointment_date,
                    entry.appointment_time,
                    entry.status,
                ),
                tags=(entry.status,),
            )
        if selected_token in self.entries_by_token:
            self.tree.selection_set(str(selected_token))
            self.tree.focus(str(selected_token))
        self.summary_var.set(f"{len(entries)} appointment(s) match these filters.")
        self._selection_changed()

    def _selection_changed(self, _event: tk.Event | None = None) -> None:
        entry = self._selected_entry()
        self.done_button.configure(
            state="normal" if entry and entry.status == "In Consultation" else "disabled"
        )
        self.cancel_button.configure(
            state="normal" if entry and entry.status == "Waiting" else "disabled"
        )
