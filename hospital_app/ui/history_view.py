"""Searchable appointment history with note editing."""

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from hospital_app.models import QueueEntry


class HistoryView(ttk.Frame):
    ALL_STATUSES = "All statuses"

    def __init__(
        self,
        parent: tk.Misc,
        on_search: Callable[[str, str, str], None],
        on_update_notes: Callable[[int, str], None],
        on_delete: Callable[[int], None],
    ) -> None:
        super().__init__(parent, padding=18)
        self.on_search = on_search
        self.on_update_notes = on_update_notes
        self.on_delete = on_delete
        self.entries: dict[int, QueueEntry] = {}
        self.search_var = tk.StringVar()
        self.date_var = tk.StringVar()
        self.status_var = tk.StringVar(value=self.ALL_STATUSES)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        ttk.Label(
            self, text="Appointment History", font=("Segoe UI", 19, "bold")
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        filters = ttk.LabelFrame(self, text="Search and filters", padding=10)
        filters.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        filters.columnconfigure(0, weight=1)
        search = ttk.Entry(
            filters,
            textvariable=self.search_var,
        )
        search.grid(row=0, column=0, sticky="ew", padx=(0, 7))
        search.bind("<Return>", self._search)
        ttk.Label(filters, text="Date (YYYY-MM-DD)").grid(
            row=0, column=1, padx=(0, 5)
        )
        ttk.Entry(filters, textvariable=self.date_var, width=14).grid(
            row=0, column=2, padx=(0, 7)
        )
        self.status_combo = ttk.Combobox(
            filters,
            textvariable=self.status_var,
            values=(self.ALL_STATUSES, "Waiting", "In Consultation", "Completed", "Cancelled"),
            state="readonly",
            width=18,
        )
        self.status_combo.grid(row=0, column=3, padx=(0, 7))
        ttk.Button(filters, text="Search", command=self._search).grid(
            row=0, column=4, padx=(0, 6)
        )
        ttk.Button(filters, text="Clear filters", command=self._clear).grid(
            row=0, column=5
        )

        table_frame = ttk.LabelFrame(self, text="All appointments", padding=10)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        columns = (
            "token",
            "patient",
            "doctor",
            "department",
            "date",
            "time",
            "status",
            "notes",
        )
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        for key, title, width in (
            ("token", "Token", 70),
            ("patient", "Patient", 150),
            ("doctor", "Doctor", 130),
            ("department", "Department", 140),
            ("date", "Date", 105),
            ("time", "Time", 85),
            ("status", "Status", 125),
            ("notes", "Notes", 230),
        ):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=55, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(
            table_frame, orient="horizontal", command=self.tree.xview
        )
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.bind("<<TreeviewSelect>>", self._select)

        notes = ttk.LabelFrame(self, text="Update selected appointment notes", padding=10)
        notes.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        notes.columnconfigure(0, weight=1)
        self.notes_text = tk.Text(notes, height=3, wrap="word", font=("Segoe UI", 9))
        self.notes_text.grid(row=0, column=0, sticky="ew")
        self.save_notes = ttk.Button(
            notes, text="Save Notes", command=self._save_notes, state="disabled"
        )
        self.save_notes.grid(row=0, column=1, padx=(8, 0), sticky="ns")
        self.delete_button = ttk.Button(
            notes, text="Delete Appointment", command=self._delete, state="disabled"
        )
        self.delete_button.grid(row=0, column=2, padx=(8, 0), sticky="ns")

    def _search(self, _event: tk.Event | None = None) -> None:
        status = self.status_var.get()
        self.on_search(
            self.search_var.get().strip(),
            self.date_var.get().strip(),
            "" if status == self.ALL_STATUSES else status,
        )

    def _clear(self) -> None:
        self.search_var.set("")
        self.date_var.set("")
        self.status_var.set(self.ALL_STATUSES)
        self._search()

    def _select(self, _event: tk.Event) -> None:
        selection = self.tree.selection()
        entry = self.entries.get(int(selection[0])) if selection else None
        self.notes_text.delete("1.0", tk.END)
        if entry is not None:
            self.notes_text.insert("1.0", entry.notes)
            self.save_notes.configure(state="normal")
            self.delete_button.configure(state="normal")
        else:
            self.save_notes.configure(state="disabled")
            self.delete_button.configure(state="disabled")

    def _save_notes(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self.on_update_notes(
            int(selection[0]), self.notes_text.get("1.0", "end-1c")
        )

    def _delete(self) -> None:
        selection = self.tree.selection()
        if selection:
            self.on_delete(int(selection[0]))

    def show_entries(self, entries: list[QueueEntry]) -> None:
        self.entries = {entry.token_no: entry for entry in entries}
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
                    entry.doctor_name,
                    entry.department,
                    entry.appointment_date,
                    entry.appointment_time,
                    entry.status,
                    entry.notes,
                ),
            )
        self._select(tk.Event())
