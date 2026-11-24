"""Doctor administration form and searchable doctor list."""

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from hospital_app.models import Doctor, DoctorInput


class DoctorForm(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        on_create: Callable[[DoctorInput], None],
        on_update: Callable[[int, DoctorInput], None],
        on_delete: Callable[[int], None],
        on_search: Callable[[str], None],
        on_refresh: Callable[[], None],
    ) -> None:
        super().__init__(parent, padding=18)
        self.on_create = on_create
        self.on_update = on_update
        self.on_delete = on_delete
        self.on_search = on_search
        self.on_refresh = on_refresh
        self.selected_id: int | None = None
        self.doctors_by_id: dict[int, Doctor] = {}
        self.name_var = tk.StringVar()
        self.dept_var = tk.StringVar()
        self.fee_var = tk.StringVar()
        self.room_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        form = ttk.LabelFrame(self, text="Doctor details", padding=14)
        form.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        for column in range(4):
            form.columnconfigure(column, weight=1)
        fields = (
            ("Doctor name", self.name_var),
            ("Department", self.dept_var),
            ("Consultation fee", self.fee_var),
            ("Room number", self.room_var),
        )
        self.entries: list[ttk.Entry] = []
        for column, (label, variable) in enumerate(fields):
            ttk.Label(form, text=label, style="Field.TLabel").grid(
                row=0, column=column, sticky="w", padx=5
            )
            entry = ttk.Entry(form, textvariable=variable)
            entry.grid(row=1, column=column, sticky="ew", padx=5, pady=(5, 0))
            self.entries.append(entry)
        actions = ttk.Frame(form)
        actions.grid(row=2, column=0, columnspan=4, sticky="w", pady=(12, 0))
        ttk.Button(
            actions,
            text="Add Doctor",
            style="Accent.TButton",
            command=self._create,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Update Doctor", command=self._update).pack(
            side="left", padx=6
        )
        ttk.Button(actions, text="Delete Doctor", command=self._delete).pack(
            side="left", padx=6
        )
        ttk.Button(actions, text="Clear Form", command=self.clear).pack(
            side="left", padx=6
        )

        table_frame = ttk.LabelFrame(self, text="Doctor directory", padding=12)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(table_frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(0, weight=1)
        search = ttk.Entry(toolbar, textvariable=self.search_var)
        search.grid(row=0, column=0, sticky="ew", padx=(0, 7))
        search.bind("<Return>", lambda _event: self.on_search(self.search_var.get()))
        ttk.Button(
            toolbar,
            text="Search Doctor",
            command=lambda: self.on_search(self.search_var.get()),
        ).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(toolbar, text="Refresh", command=self.on_refresh).grid(
            row=0, column=2
        )
        columns = ("id", "name", "department", "fee", "room")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        for key, title, width in (
            ("id", "Doctor ID", 85),
            ("name", "Doctor name", 220),
            ("department", "Department", 200),
            ("fee", "Fee (Rs.)", 120),
            ("room", "Room", 100),
        ):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=60, anchor="w")
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._select)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

    def _doctor_input(self) -> DoctorInput:
        try:
            fee = float(self.fee_var.get())
        except ValueError as error:
            raise ValueError("Consultation fee must be a valid number.") from error
        return DoctorInput(
            self.name_var.get(), self.dept_var.get(), fee, self.room_var.get()
        )

    def _create(self) -> None:
        try:
            doctor = self._doctor_input()
        except ValueError as error:
            messagebox.showerror("Invalid doctor details", str(error), parent=self)
            return
        self.on_create(doctor)

    def _update(self) -> None:
        if self.selected_id is None:
            messagebox.showwarning(
                "Select a doctor", "Select a doctor from the table first.", parent=self
            )
            return
        try:
            doctor = self._doctor_input()
        except ValueError as error:
            messagebox.showerror("Invalid doctor details", str(error), parent=self)
            return
        self.on_update(self.selected_id, doctor)

    def _delete(self) -> None:
        if self.selected_id is None:
            messagebox.showwarning(
                "Select a doctor", "Select a doctor from the table first.", parent=self
            )
            return
        self.on_delete(self.selected_id)

    def _select(self, _event: tk.Event) -> None:
        selection = self.tree.selection()
        doctor = self.doctors_by_id.get(int(selection[0])) if selection else None
        if doctor is None:
            return
        self.selected_id = doctor.doctor_id
        self.name_var.set(doctor.doc_name)
        self.dept_var.set(doctor.dept)
        self.fee_var.set(str(doctor.fee))
        self.room_var.set(doctor.room_no)

    def show_doctors(self, doctors: list[Doctor]) -> None:
        self.doctors_by_id = {doctor.doctor_id: doctor for doctor in doctors}
        for item in self.tree.get_children():
            self.tree.delete(item)
        for doctor in doctors:
            self.tree.insert(
                "",
                "end",
                iid=str(doctor.doctor_id),
                values=(
                    doctor.doctor_id,
                    doctor.doc_name,
                    doctor.dept,
                    f"{doctor.fee:,.2f}",
                    doctor.room_no,
                ),
            )
        if self.selected_id not in self.doctors_by_id:
            self.selected_id = None

    def clear(self) -> None:
        self.selected_id = None
        self.tree.selection_remove(*self.tree.selection())
        for variable in (self.name_var, self.dept_var, self.fee_var, self.room_var):
            variable.set("")
        self.entries[0].focus_set()
