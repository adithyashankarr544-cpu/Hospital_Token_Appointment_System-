"""Database access for doctors and their specializations."""

import sqlite3

from hospital_app.database import Database
from hospital_app.models import Doctor, DoctorInput


class DoctorRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _to_doctor(row: sqlite3.Row) -> Doctor:
        return Doctor(
            doctor_id=row["doctor_id"],
            doc_name=row["doc_name"],
            dept=row["dept"],
            fee=row["fee"],
            room_no=row["room_no"],
        )

    def get_all(self) -> list[Doctor]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT doctor_id, doc_name, dept, fee, room_no
                FROM doctors
                ORDER BY dept, doc_name
                """
            ).fetchall()
        return [self._to_doctor(row) for row in rows]

    def search(self, term: str = "") -> list[Doctor]:
        pattern = f"%{term.strip()}%"
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT doctor_id, doc_name, dept, fee, room_no
                FROM doctors
                WHERE ? = '' OR doc_name LIKE ? OR dept LIKE ? OR room_no LIKE ?
                ORDER BY dept, doc_name
                """,
                (term.strip(), pattern, pattern, pattern),
            ).fetchall()
        return [self._to_doctor(row) for row in rows]

    def create(self, doctor: DoctorInput) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO doctors (doc_name, dept, fee, room_no)
                VALUES (?, ?, ?, ?)
                """,
                (doctor.doc_name, doctor.dept, doctor.fee, doctor.room_no),
            )
            return int(cursor.lastrowid)

    def update(self, doctor_id: int, doctor: DoctorInput) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE doctors SET doc_name = ?, dept = ?, fee = ?, room_no = ?
                WHERE doctor_id = ?
                """,
                (doctor.doc_name, doctor.dept, doctor.fee, doctor.room_no, doctor_id),
            )
            return cursor.rowcount == 1

    def delete(self, doctor_id: int) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM doctors WHERE doctor_id = ?", (doctor_id,)
            )
            return cursor.rowcount == 1

    def get_departments(self) -> list[str]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT dept FROM doctors ORDER BY dept"
            ).fetchall()
        return [row["dept"] for row in rows]

    def get_by_id(self, doctor_id: int) -> Doctor | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT doctor_id, doc_name, dept, fee, room_no
                FROM doctors
                WHERE doctor_id = ?
                """,
                (doctor_id,),
            ).fetchone()
        return self._to_doctor(row) if row else None
