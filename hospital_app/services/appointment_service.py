"""Validation and business rules for patient appointments and queue actions."""

import re
from datetime import datetime
from math import isfinite

from hospital_app.models import Doctor, DoctorInput, PatientInput, QueueEntry
from hospital_app.repositories.appointment_repository import AppointmentRepository
from hospital_app.repositories.doctor_repository import DoctorRepository
from hospital_app.repositories.patient_repository import PatientRepository


VALID_BLOOD_GROUPS = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
VALID_GENDERS = {"Female", "Male", "Other"}


class AppointmentService:
    def __init__(
        self,
        doctor_repository: DoctorRepository,
        patient_repository: PatientRepository,
        appointment_repository: AppointmentRepository,
    ) -> None:
        self.doctor_repository = doctor_repository
        self.patient_repository = patient_repository
        self.appointment_repository = appointment_repository

    def register_appointment(
        self,
        patient: PatientInput,
        doctor_id: int,
        appointment_date: str,
        appointment_time: str,
        notes: str,
    ) -> int:
        self._validate_patient(patient)
        if self.doctor_repository.get_by_id(doctor_id) is None:
            raise ValueError("Please select an available doctor.")
        notes = self._validate_appointment(appointment_date, appointment_time, notes)
        patient_id = self.patient_repository.create(self._normalize_patient(patient))
        return self.appointment_repository.create(
            doctor_id, patient_id, appointment_date, appointment_time, notes
        )

    def register_patient(self, patient: PatientInput) -> int:
        self._validate_patient(patient)
        return self.patient_repository.create(self._normalize_patient(patient))

    def book_existing_patient(
        self,
        patient_id: int,
        doctor_id: int,
        appointment_date: str,
        appointment_time: str,
        notes: str,
    ) -> int:
        if self.patient_repository.get_by_id(patient_id) is None:
            raise ValueError("Please select a registered patient.")
        if self.doctor_repository.get_by_id(doctor_id) is None:
            raise ValueError("Please select an available doctor.")
        notes = self._validate_appointment(appointment_date, appointment_time, notes)
        return self.appointment_repository.create(
            doctor_id, patient_id, appointment_date, appointment_time, notes
        )

    def update_patient(self, patient_id: int, patient: PatientInput) -> bool:
        self._validate_patient(patient)
        return self.patient_repository.update(
            patient_id, self._normalize_patient(patient)
        )

    def get_queue(
        self,
        doctor_id: int | None = None,
        search: str = "",
        status: str | None = None,
        appointment_date: str | None = None,
    ) -> list[QueueEntry]:
        return self.appointment_repository.get_queue(
            doctor_id, search, status, appointment_date
        )

    def create_doctor(self, doctor: DoctorInput) -> int:
        normalized = self._validate_doctor(doctor)
        if any(
            item.doc_name.casefold() == normalized.doc_name.casefold()
            and item.dept.casefold() == normalized.dept.casefold()
            for item in self.doctor_repository.get_all()
        ):
            raise ValueError("A doctor with this name and department already exists.")
        return self.doctor_repository.create(normalized)

    def update_doctor(self, doctor_id: int, doctor: DoctorInput) -> bool:
        if self.doctor_repository.get_by_id(doctor_id) is None:
            raise ValueError("The selected doctor no longer exists.")
        normalized = self._validate_doctor(doctor)
        if any(
            item.doctor_id != doctor_id
            and item.doc_name.casefold() == normalized.doc_name.casefold()
            and item.dept.casefold() == normalized.dept.casefold()
            for item in self.doctor_repository.get_all()
        ):
            raise ValueError("A doctor with this name and department already exists.")
        return self.doctor_repository.update(doctor_id, normalized)

    def delete_doctor(self, doctor_id: int) -> bool:
        return self.doctor_repository.delete(doctor_id)

    def call_next(self, doctor_id: int | None = None) -> int | None:
        if doctor_id is not None and self.doctor_repository.get_by_id(doctor_id) is None:
            raise ValueError("Please select an available doctor.")
        return self.appointment_repository.call_next(doctor_id)

    def mark_done(self, token_no: int) -> None:
        if not self.appointment_repository.mark_done(token_no):
            raise ValueError("Only an appointment in consultation can be marked done.")

    def cancel_appointment(self, token_no: int) -> None:
        if not self.appointment_repository.cancel(token_no):
            raise ValueError("Only a waiting appointment can be cancelled.")

    @staticmethod
    def _normalize_patient(patient: PatientInput) -> PatientInput:
        return PatientInput(
            name=patient.name.strip(),
            age=patient.age,
            phone=patient.phone.strip(),
            blood_group=patient.blood_group or None,
            gender=patient.gender,
        )

    @staticmethod
    def _validate_patient(patient: PatientInput) -> None:
        name = patient.name.strip()
        phone = patient.phone.strip()
        if not name:
            raise ValueError("Patient name cannot be empty.")
        if not 1 <= patient.age <= 120:
            raise ValueError("Age must be between 1 and 120.")
        if not re.fullmatch(r"[0-9]{7,15}", phone):
            raise ValueError("Phone number must contain 7 to 15 digits.")
        if patient.gender not in VALID_GENDERS:
            raise ValueError("Please select a valid gender.")
        if patient.blood_group and patient.blood_group not in VALID_BLOOD_GROUPS:
            raise ValueError("Please select a valid blood group.")

    @staticmethod
    def _validate_doctor(doctor: DoctorInput) -> DoctorInput:
        name, department, room = (
            doctor.doc_name.strip(),
            doctor.dept.strip(),
            doctor.room_no.strip(),
        )
        if not name:
            raise ValueError("Doctor name cannot be empty.")
        if not department:
            raise ValueError("Department cannot be empty.")
        if not isfinite(doctor.fee) or doctor.fee < 0:
            raise ValueError("Consultation fee must be a non-negative number.")
        if not room:
            raise ValueError("Room number cannot be empty.")
        return DoctorInput(name, department, doctor.fee, room)

    @staticmethod
    def _validate_appointment(
        appointment_date: str, appointment_time: str, notes: str
    ) -> str:
        try:
            scheduled = datetime.strptime(
                f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M"
            )
        except ValueError as error:
            raise ValueError(
                "Enter a valid appointment date (YYYY-MM-DD) and time (HH:MM)."
            ) from error
        if scheduled < datetime.now().replace(second=0, microsecond=0):
            raise ValueError("Appointment date and time cannot be in the past.")
        notes = notes.strip()
        if len(notes) > 500:
            raise ValueError("Appointment notes cannot exceed 500 characters.")
        return notes
