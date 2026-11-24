"""Database access for registered patients."""

from hospital_app.database import Database
from hospital_app.models import Patient, PatientInput


class PatientRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, patient: PatientInput) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO patients (name, age, phone, blood_group, gender)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    patient.name,
                    patient.age,
                    patient.phone,
                    patient.blood_group,
                    patient.gender,
                ),
            )
            return cursor.lastrowid

    def update(self, patient_id: int, patient: PatientInput) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE patients
                SET name = ?, age = ?, phone = ?, blood_group = ?, gender = ?
                WHERE patient_id = ?
                """,
                (
                    patient.name,
                    patient.age,
                    patient.phone,
                    patient.blood_group,
                    patient.gender,
                    patient_id,
                ),
            )
            return cursor.rowcount == 1

    def delete(self, patient_id: int) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM patients WHERE patient_id = ?", (patient_id,)
            )
            return cursor.rowcount == 1

    def get_by_id(self, patient_id: int) -> Patient | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT patient_id, name, age, phone, blood_group, gender
                FROM patients WHERE patient_id = ?
                """,
                (patient_id,),
            ).fetchone()
        if row is None:
            return None
        return Patient(
            patient_id=row["patient_id"],
            name=row["name"],
            age=row["age"],
            phone=row["phone"],
            blood_group=row["blood_group"],
            gender=row["gender"],
        )

    def get_all(self, search: str = "") -> list[Patient]:
        pattern = f"%{search.strip()}%"
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT patient_id, name, age, phone, blood_group, gender
                FROM patients
                WHERE ? = '' OR name LIKE ? OR phone LIKE ?
                ORDER BY name, patient_id
                """,
                (search.strip(), pattern, pattern),
            ).fetchall()
        return [
            Patient(
                patient_id=row["patient_id"],
                name=row["name"],
                age=row["age"],
                phone=row["phone"],
                blood_group=row["blood_group"],
                gender=row["gender"],
            )
            for row in rows
        ]

    def get_recent(self, limit: int = 8) -> list[Patient]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT patient_id, name, age, phone, blood_group, gender
                FROM patients ORDER BY patient_id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            Patient(
                patient_id=row["patient_id"],
                name=row["name"],
                age=row["age"],
                phone=row["phone"],
                blood_group=row["blood_group"],
                gender=row["gender"],
            )
            for row in rows
        ]
