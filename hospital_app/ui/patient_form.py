"""Patient registration, editing, search, and deletion controls."""

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from hospital_app.models import Patient, PatientInput


class PatientForm(ttk.LabelFrame):
    def __init__(
        self,
        parent: tk.Misc,
        on_create: Callable[[PatientInput], None],
        on_update: Callable[[int, PatientInput], None],
        on_delete: Callable[[int], None],
        on_search: Callable[[str], None],
        on_refresh: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, text="  Patient Registration  ", padding=14)
        self.on_create = on_create
        self.on_update = on_update
        self.on_delete = on_delete
        self.on_search = on_search
        self.on_refresh = on_refresh
        self.selected_patient_id: int | None = None

        self.name_var = tk.StringVar()
        self.age_var = tk.StringVar(value="18")
        self.phone_var = tk.StringVar()
        self.blood_group_var = tk.StringVar()
        self.gender_var = tk.StringVar()
        self.search_var = tk.StringVar()

        self.columnconfigure(1, weight=1)
        self.rowconfigure(8, weight=1)
        self._add_label(0, "Patient name")
        self.name_entry = ttk.Entry(self, textvariable=self.name_var)
        self.name_entry.grid(
            row=0, column=1, sticky="ew", pady=4
        )
        self._add_label(1, "Age")
        ttk.Spinbox(
            self, from_=1, to=120, textvariable=self.age_var, width=8
        ).grid(row=1, column=1, sticky="w", pady=4)
        self._add_label(2, "Phone number")
        ttk.Entry(self, textvariable=self.phone_var).grid(
            row=2, column=1, sticky="ew", pady=4
        )
        self._add_label(3, "Blood group")
        ttk.Combobox(
            self,
            textvariable=self.blood_group_var,
            values=("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"),
            state="readonly",
        ).grid(row=3, column=1, sticky="ew", pady=4)
        self._add_label(4, "Gender")
        genders = ttk.Frame(self)
        genders.grid(row=4, column=1, sticky="w", pady=4)
        for gender in ("Male", "Female", "Other"):
            ttk.Radiobutton(
                genders, text=gender, value=gender, variable=self.gender_var
            ).pack(side="left", padx=(0, 9))

        actions = ttk.Frame(self)
        actions.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 10))
        for column in range(4):
            actions.columnconfigure(column, weight=1)
        ttk.Button(
            actions, text="Register", style="Accent.TButton", command=self._create
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(actions, text="Update", command=self._update).grid(
            row=0, column=1, sticky="ew", padx=4
        )
        ttk.Button(actions, text="Delete", command=self._delete).grid(
            row=0, column=2, sticky="ew", padx=4
        )
        ttk.Button(actions, text="Clear", command=self.clear).grid(
            row=0, column=3, sticky="ew", padx=(4, 0)
        )

        ttk.Label(self, text="Registered patients", style="Field.TLabel").grid(
            row=6, column=0, sticky="w", pady=(2, 5)
        )
        search_bar = ttk.Frame(self)
        search_bar.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        search_bar.columnconfigure(0, weight=1)
        self.search_entry = ttk.Entry(search_bar, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.search_entry.bind(
            "<Return>", lambda _event: self.on_search(self.search_var.get())
        )
        ttk.Button(
            search_bar,
            text="Search",
            command=lambda: self.on_search(self.search_var.get()),
        ).grid(row=0, column=1, padx=(0, 6))
        if self.on_refresh is not None:
            ttk.Button(
                search_bar, text="Refresh", command=self.on_refresh
            ).grid(row=0, column=2)

        columns = ("id", "name", "age", "phone", "blood", "gender")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=7)
        for column, heading, width in (
            ("id", "ID", 48),
            ("name", "Name", 138),
            ("age", "Age", 48),
            ("phone", "Phone", 112),
            ("blood", "Blood", 60),
            ("gender", "Gender", 76),
        ):
            self.tree.heading(column, text=heading)
            self.tree.column(
                column,
                width=width,
                minwidth=40,
                anchor="center" if column in {"id", "age"} else "w",
            )
        self.tree.grid(row=8, column=0, columnspan=2, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._select_patient)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=8, column=2, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

    def _add_label(self, row: int, text: str) -> None:
        ttk.Label(self, text=text, style="Field.TLabel").grid(
            row=row, column=0, sticky="w", padx=(0, 10), pady=4
        )

    def _patient_input(self) -> PatientInput:
        return PatientInput(
            name=self.name_var.get(),
            age=int(self.age_var.get()),
            phone=self.phone_var.get(),
            blood_group=self.blood_group_var.get(),
            gender=self.gender_var.get(),
        )

    def _create(self) -> None:
        patient = self._get_patient_input()
        if patient is not None:
            self.on_create(patient)

    def _update(self) -> None:
        if self.selected_patient_id is not None:
            patient = self._get_patient_input()
            if patient is not None:
                self.on_update(self.selected_patient_id, patient)

    def _delete(self) -> None:
        if self.selected_patient_id is not None:
            self.on_delete(self.selected_patient_id)

    def _select_patient(self, _event: tk.Event) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        patient = self.patient_by_id.get(int(selection[0]))
        if patient is None:
            return
        self.selected_patient_id = patient.patient_id
        self.name_var.set(patient.name)
        self.age_var.set(str(patient.age))
        self.phone_var.set(patient.phone)
        self.blood_group_var.set(patient.blood_group)
        self.gender_var.set(patient.gender)

    def _get_patient_input(self) -> PatientInput | None:
        try:
            return self._patient_input()
        except ValueError:
            messagebox.showerror(
                "Invalid age", "Enter a whole number for age.", parent=self
            )
            return None

    def show_patients(self, patients: list[Patient]) -> None:
        self.patient_by_id = {patient.patient_id: patient for patient in patients}
        for item in self.tree.get_children():
            self.tree.delete(item)
        for patient in patients:
            self.tree.insert(
                "",
                "end",
                iid=str(patient.patient_id),
                values=(
                    patient.patient_id,
                    patient.name,
                    patient.age,
                    patient.phone,
                    patient.blood_group or "",
                    patient.gender,
                ),
            )
        if self.selected_patient_id not in self.patient_by_id:
            self.selected_patient_id = None

    def select_patient(self, patient_id: int) -> None:
        if patient_id in self.patient_by_id:
            self.tree.selection_set(str(patient_id))
            self.tree.focus(str(patient_id))
            self._select_patient(tk.Event())

    def clear(self) -> None:
        self.selected_patient_id = None
        self.tree.selection_remove(*self.tree.selection())
        self.search_var.set("")
        self.name_var.set("")
        self.age_var.set("18")
        self.phone_var.set("")
        self.blood_group_var.set("")
        self.gender_var.set("")
        self.name_entry.focus_set()
