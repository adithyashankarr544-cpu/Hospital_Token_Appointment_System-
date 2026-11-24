"""Temporary-database tests for the hospital management workflows."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from hospital_app.database import Database, SAMPLE_DOCTORS
from hospital_app.models import DoctorInput, PatientInput
from hospital_app.repositories.appointment_repository import AppointmentRepository
from hospital_app.repositories.doctor_repository import DoctorRepository
from hospital_app.repositories.patient_repository import PatientRepository
from hospital_app.services.appointment_service import AppointmentService


class HospitalWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = Database(self.root / "hospital_management.db")
        self.database.initialize()
        self.doctors = DoctorRepository(self.database)
        self.patients = PatientRepository(self.database)
        self.appointments = AppointmentRepository(self.database)
        self.service = AppointmentService(
            self.doctors, self.patients, self.appointments
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def patient(name: str = "Asha Rao", phone: str = "9876543210") -> PatientInput:
        return PatientInput(name, 32, phone, "O+", "Female")

    @staticmethod
    def schedule(minutes_from_now: int = 30) -> tuple[str, str]:
        scheduled = datetime.now().replace(second=0, microsecond=0) + timedelta(
            minutes=minutes_from_now
        )
        return scheduled.date().isoformat(), scheduled.strftime("%H:%M")

    def test_initialization_seeds_sample_doctors_once_and_enables_foreign_keys(
        self,
    ) -> None:
        self.database.initialize()
        self.assertEqual(len(self.doctors.get_all()), len(SAMPLE_DOCTORS))
        with self.database.connect() as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(appointments)")
            }
        self.assertTrue({"appointment_date", "appointment_time"}.issubset(columns))

    def test_patient_registration_update_search_and_safe_deletion(self) -> None:
        patient_id = self.service.register_patient(self.patient())
        self.assertEqual(
            [patient.patient_id for patient in self.patients.get_all("Asha")],
            [patient_id],
        )
        self.assertEqual(
            [patient.patient_id for patient in self.patients.get_all("98765")],
            [patient_id],
        )
        self.service.update_patient(
            patient_id, PatientInput("Asha R.", 33, "9876543210", None, "Female")
        )
        self.assertEqual(self.patients.get_by_id(patient_id).name, "Asha R.")
        self.assertIsNone(self.patients.get_by_id(patient_id).blood_group)

        doctor_id = self.doctors.get_all()[0].doctor_id
        day, time = self.schedule()
        token = self.service.book_existing_patient(
            patient_id, doctor_id, day, time, "Follow-up"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.patients.delete(patient_id)
        self.assertTrue(self.appointments.delete(token))
        self.assertTrue(self.patients.delete(patient_id))

    def test_booking_token_conflicts_queue_transitions_filters_and_history(self) -> None:
        patient_id = self.service.register_patient(self.patient())
        doctor_id = self.doctors.get_all()[0].doctor_id
        other_doctor_id = self.doctors.get_all()[1].doctor_id
        day, time = self.schedule()
        token = self.service.book_existing_patient(
            patient_id, doctor_id, day, time, "First visit"
        )
        with self.assertRaisesRegex(ValueError, "already has an appointment"):
            self.service.book_existing_patient(patient_id, doctor_id, day, time, "")

        day2, time2 = self.schedule(45)
        next_token = self.service.book_existing_patient(
            patient_id, doctor_id, day2, time2, "Second visit"
        )
        other_token = self.service.book_existing_patient(
            patient_id, other_doctor_id, day, time, "Different doctor"
        )
        self.assertEqual(self.service.call_next(doctor_id), token)
        self.service.mark_done(token)
        with self.assertRaisesRegex(ValueError, "[Oo]nly an appointment"):
            self.service.mark_done(token)
        self.service.cancel_appointment(next_token)
        self.assertEqual(self.service.call_next(doctor_id), None)
        self.assertEqual(self.service.call_next(other_doctor_id), other_token)
        self.assertEqual(
            {entry.token_no for entry in self.service.get_queue(doctor_id=doctor_id)},
            {token, next_token},
        )
        self.assertEqual(
            [entry.token_no for entry in self.service.get_queue(search=str(token))],
            [token],
        )
        self.assertEqual(
            [entry.token_no for entry in self.service.get_queue(status="Cancelled")],
            [next_token],
        )
        self.assertEqual(
            {
                entry.token_no
                for entry in self.service.get_queue(appointment_date=day)
            },
            {token, other_token}
            | ({next_token} if day2 == day else set()),
        )
        states = {
            entry.token_no: entry.status for entry in self.service.get_queue()
        }
        self.assertEqual(states[token], "Completed")
        self.assertEqual(states[next_token], "Cancelled")
        self.assertEqual(states[other_token], "In Consultation")
        self.assertEqual(self.appointments.get_by_token(token).notes, "First visit")
        _, waiting, consulting, completed = self.appointments.get_dashboard_counts()
        self.assertEqual(waiting, 0)
        self.assertEqual(consulting, 1)
        self.assertEqual(completed, 1)
        self.assertTrue(self.appointments.update_notes(token, "Updated note"))
        self.assertEqual(self.appointments.get_by_token(token).notes, "Updated note")

    def test_patient_appointment_and_doctor_validation(self) -> None:
        invalid_patients = (
            PatientInput("", 22, "9876543210", "O+", "Male"),
            PatientInput("Test", 0, "9876543210", "O+", "Male"),
            PatientInput("Test", 22, "12x", "O+", "Male"),
            PatientInput("Test", 22, "9876543210", "O+", ""),
            PatientInput("Test", 22, "9876543210", "bad", "Male"),
        )
        for patient in invalid_patients:
            with self.subTest(patient=patient):
                with self.assertRaises(ValueError):
                    self.service.register_patient(patient)

        for doctor in (
            DoctorInput("", "General", 100, "1"),
            DoctorInput("Doctor", "", 100, "1"),
            DoctorInput("Doctor", "General", -1, "1"),
            DoctorInput("Doctor", "General", 100, ""),
        ):
            with self.subTest(doctor=doctor):
                with self.assertRaises(ValueError):
                    self.service.create_doctor(doctor)

        patient_id = self.service.register_patient(self.patient())
        doctor_id = self.doctors.get_all()[0].doctor_id
        with self.assertRaisesRegex(ValueError, "valid appointment"):
            self.service.book_existing_patient(patient_id, doctor_id, "", "", "")
        past = (datetime.now() - timedelta(days=1)).replace(second=0).strftime(
            "%Y-%m-%d %H:%M"
        )
        with self.assertRaisesRegex(ValueError, "cannot be in the past"):
            self.service.book_existing_patient(
                patient_id, doctor_id, past[:10], past[11:], ""
            )

    def test_doctor_crud_and_appointment_relationship_protection(self) -> None:
        doctor_id = self.service.create_doctor(
            DoctorInput("Dr. Test", "Test Department", 250, "T1")
        )
        self.assertEqual(
            self.doctors.get_by_id(doctor_id).doc_name, "Dr. Test"
        )
        self.service.update_doctor(
            doctor_id, DoctorInput("Dr. Test Updated", "Test Department", 300, "T2")
        )
        patient_id = self.service.register_patient(self.patient())
        day, time = self.schedule()
        token = self.service.book_existing_patient(
            patient_id, doctor_id, day, time, ""
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.delete_doctor(doctor_id)
        self.assertIn("Dr. Test Updated", [doctor.doc_name for doctor in self.doctors.search("Updated")])
        self.assertTrue(self.appointments.delete(token))
        self.assertTrue(self.service.delete_doctor(doctor_id))
        self.assertIsNone(self.doctors.get_by_id(doctor_id))

    def test_records_persist_after_reopening_database(self) -> None:
        patient_id = self.service.register_patient(self.patient())
        reopened = Database(self.database.database_path)
        self.assertEqual(reopened.initialize(), None)
        self.assertIsNotNone(PatientRepository(reopened).get_by_id(patient_id))
        self.assertEqual(len(DoctorRepository(reopened).get_all()), 5)

    def test_legacy_schema_and_database_import_are_migrated_once(self) -> None:
        legacy_path = self.root / "legacy.db"
        legacy = sqlite3.connect(legacy_path)
        legacy.executescript(
            """
            CREATE TABLE doctors (
                doctor_id INTEGER PRIMARY KEY,
                doc_name TEXT NOT NULL, dept TEXT NOT NULL,
                fee REAL NOT NULL, room_no TEXT NOT NULL
            );
            CREATE TABLE patients (
                patient_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL, age INTEGER NOT NULL, phone TEXT NOT NULL,
                blood_group TEXT, gender TEXT NOT NULL
            );
            CREATE TABLE appointments (
                token_no INTEGER PRIMARY KEY,
                doctor_id INTEGER NOT NULL, patient_id INTEGER NOT NULL,
                token_time TEXT NOT NULL, status TEXT NOT NULL, notes TEXT
            );
            INSERT INTO doctors VALUES (1, 'Dr. Old', 'Legacy', 450, 'L1');
            INSERT INTO patients VALUES (1, 'Legacy Patient', 40, '9000000000', 'A+', 'Other');
            INSERT INTO appointments VALUES (
                1, 1, 1, '2026-01-02T09:30:00+05:30', 'Done', 'Imported notes'
            );
            """
        )
        legacy.commit()
        legacy.close()
        target = Database(self.root / "migrated.db", legacy_path)
        target.initialize()
        target.initialize()
        patients = PatientRepository(target).get_all("Legacy")
        appointments = AppointmentRepository(target).get_queue(search="Legacy")
        doctors = DoctorRepository(target).search("Dr. Old")
        self.assertEqual(len(patients), 1)
        self.assertEqual(len(doctors), 1)
        self.assertEqual(len(appointments), 1)
        self.assertEqual(appointments[0].status, "Completed")
        self.assertEqual(appointments[0].appointment_date, "2026-01-02")
        self.assertEqual(appointments[0].appointment_time, "09:30")
        self.assertEqual(appointments[0].notes, "Imported notes")

    def test_existing_database_schema_migration_preserves_rows_and_token_status(self) -> None:
        old_path = self.root / "old_schema.db"
        old = sqlite3.connect(old_path)
        old.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE doctors (
                doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_name TEXT NOT NULL, dept TEXT NOT NULL,
                fee REAL NOT NULL, room_no TEXT NOT NULL,
                UNIQUE(doc_name, dept)
            );
            CREATE TABLE patients (
                patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, age INTEGER NOT NULL, phone TEXT NOT NULL,
                blood_group TEXT NOT NULL, gender TEXT NOT NULL
            );
            CREATE TABLE appointments (
                token_no INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_id INTEGER NOT NULL, patient_id INTEGER NOT NULL,
                token_time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Waiting'
                    CHECK(status IN ('Waiting', 'Called', 'Done')),
                notes TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(doctor_id) REFERENCES doctors(doctor_id),
                FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
            );
            INSERT INTO doctors VALUES (1, 'Dr. Arun', 'General Medicine', 500, '101');
            INSERT INTO patients VALUES (1, 'Existing Patient', 50, '9111111111', 'B+', 'Male');
            INSERT INTO appointments VALUES (
                7, 1, 1, '2026-01-02T09:30:00+05:30', 'Done', 'Existing notes'
            );
            """
        )
        old.commit()
        old.close()

        migrated = Database(old_path)
        migrated.initialize()
        patient_rows = PatientRepository(migrated).get_all("Existing Patient")
        appointment = AppointmentRepository(migrated).get_by_token(7)
        self.assertEqual(len(patient_rows), 1)
        self.assertEqual(patient_rows[0].patient_id, 1)
        self.assertEqual(appointment.status, "Completed")
        self.assertEqual(appointment.appointment_date, "2026-01-02")
        self.assertEqual(appointment.appointment_time, "09:30")
        self.assertEqual(appointment.notes, "Existing notes")
        self.assertEqual(
            sum(doctor.doc_name == "Dr. Arun" for doctor in DoctorRepository(migrated).get_all()),
            1,
        )


if __name__ == "__main__":
    unittest.main()
