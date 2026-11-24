"""Typed data structures shared by repositories, services, and the UI."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Doctor:
    doctor_id: int
    doc_name: str
    dept: str
    fee: float
    room_no: str

    @property
    def display_name(self) -> str:
        return f"{self.doc_name} - {self.dept}"


@dataclass(frozen=True)
class DoctorInput:
    doc_name: str
    dept: str
    fee: float
    room_no: str


@dataclass(frozen=True)
class PatientInput:
    name: str
    age: int
    phone: str
    blood_group: str | None
    gender: str


@dataclass(frozen=True)
class Patient:
    patient_id: int
    name: str
    age: int
    phone: str
    blood_group: str | None
    gender: str


@dataclass(frozen=True)
class DashboardStats:
    total_patients: int
    total_doctors: int
    todays_appointments: int
    waiting_patients: int
    in_consultation: int
    completed_consultations: int


@dataclass(frozen=True)
class QueueEntry:
    token_no: int
    patient_name: str
    age: int
    gender: str
    phone: str
    doctor_name: str
    department: str
    room_no: str
    appointment_date: str
    appointment_time: str
    token_time: str
    status: str
    notes: str
