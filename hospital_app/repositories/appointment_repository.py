"""Database access for appointments and live queue transitions."""

from datetime import datetime
from hospital_app.database import Database
from hospital_app.models import QueueEntry

STATUSES = ("Waiting", "In Consultation", "Completed", "Cancelled")


class AppointmentRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        doctor_id: int,
        patient_id: int,
        appointment_date: str,
        appointment_time: str,
        notes: str,
    ) -> int:
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            conflict = connection.execute(
                """
                SELECT token_no FROM appointments
                WHERE doctor_id = ? AND appointment_date = ? AND appointment_time = ?
                    AND status != 'Cancelled'
                LIMIT 1
                """,
                (doctor_id, appointment_date, appointment_time),
            ).fetchone()
            if conflict:
                raise ValueError(
                    "This doctor already has an appointment at that date and time."
                )
            cursor = connection.execute(
                """
                INSERT INTO appointments
                    (doctor_id, patient_id, appointment_date, appointment_time,
                     token_time, status, notes)
                VALUES (?, ?, ?, ?, ?, 'Waiting', ?)
                """,
                (
                    doctor_id,
                    patient_id,
                    appointment_date,
                    appointment_time,
                    datetime.now().astimezone().isoformat(timespec="seconds"),
                    notes,
                ),
            )
            return int(cursor.lastrowid)

    def get_queue(
        self,
        doctor_id: int | None = None,
        search: str = "",
        status: str | None = None,
        appointment_date: str | None = None,
    ) -> list[QueueEntry]:
        query = """
            SELECT a.token_no, p.name AS patient_name, p.age, p.gender, p.phone,
                   d.doc_name AS doctor_name, d.dept AS department, d.room_no,
                   a.appointment_date, a.appointment_time,
                   a.token_time, a.status, a.notes
            FROM appointments AS a
            JOIN patients AS p ON p.patient_id = a.patient_id
            JOIN doctors AS d ON d.doctor_id = a.doctor_id
        """
        conditions: list[str] = []
        parameters: list[object] = []
        if doctor_id is not None:
            conditions.append("a.doctor_id = ?")
            parameters.append(doctor_id)
        if status in STATUSES:
            conditions.append("a.status = ?")
            parameters.append(status)
        if appointment_date:
            conditions.append("a.appointment_date = ?")
            parameters.append(appointment_date)
        if search.strip():
            term = search.strip()
            if term.isdigit():
                conditions.append(
                    """
                    (
                        CAST(a.token_no AS TEXT) = ?
                        OR (
                            NOT EXISTS (
                                SELECT 1 FROM appointments
                                WHERE CAST(token_no AS TEXT) = ?
                            )
                            AND (
                                p.name LIKE ? OR p.phone LIKE ? OR d.doc_name LIKE ?
                            )
                        )
                    )
                    """
                )
                pattern = f"%{term}%"
                parameters.extend((term, term, pattern, pattern, pattern))
            else:
                conditions.append(
                    "(p.name LIKE ? OR p.phone LIKE ? OR d.doc_name LIKE ?)"
                )
                pattern = f"%{term}%"
                parameters.extend((pattern, pattern, pattern))
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += """
            ORDER BY a.appointment_date, a.appointment_time, a.token_no
        """
        with self.database.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            QueueEntry(
                token_no=row["token_no"],
                patient_name=row["patient_name"],
                age=row["age"],
                gender=row["gender"],
                phone=row["phone"],
                doctor_name=row["doctor_name"],
                department=row["department"],
                room_no=row["room_no"],
                appointment_date=row["appointment_date"],
                appointment_time=row["appointment_time"],
                token_time=row["token_time"],
                status=row["status"],
                notes=row["notes"],
            )
            for row in rows
        ]

    def call_next(self, doctor_id: int | None = None) -> int | None:
        """Atomically mark the earliest waiting appointment as in consultation."""
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            doctor_filter = "AND doctor_id = ?" if doctor_id is not None else ""
            parameters = (doctor_id,) if doctor_id is not None else ()
            row = connection.execute(
                f"""
                SELECT token_no
                FROM appointments
                WHERE status = 'Waiting' {doctor_filter}
                ORDER BY appointment_date, appointment_time, token_no
                LIMIT 1
                """,
                parameters,
            ).fetchone()
            if row is None:
                return None

            connection.execute(
                """
                UPDATE appointments
                SET status = 'In Consultation'
                WHERE token_no = ? AND status = 'Waiting'
                """,
                (row["token_no"],),
            )
            return row["token_no"]

    def mark_done(self, token_no: int) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE appointments
                SET status = 'Completed'
                WHERE token_no = ? AND status = 'In Consultation'
                """,
                (token_no,),
            )
            return cursor.rowcount == 1

    def cancel(self, token_no: int) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE appointments
                SET status = 'Cancelled'
                WHERE token_no = ? AND status = 'Waiting'
                """,
                (token_no,),
            )
            return cursor.rowcount == 1

    def delete(self, token_no: int) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM appointments WHERE token_no = ?", (token_no,)
            )
            return cursor.rowcount == 1

    def update_notes(self, token_no: int, notes: str) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "UPDATE appointments SET notes = ? WHERE token_no = ?",
                (notes, token_no),
            )
            return cursor.rowcount == 1

    def get_by_token(self, token_no: int) -> QueueEntry | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT a.token_no, p.name AS patient_name, p.age, p.gender, p.phone,
                       d.doc_name AS doctor_name, d.dept AS department, d.room_no,
                       a.appointment_date, a.appointment_time, a.token_time,
                       a.status, a.notes
                FROM appointments a
                JOIN patients p ON p.patient_id = a.patient_id
                JOIN doctors d ON d.doctor_id = a.doctor_id
                WHERE a.token_no = ?
                """,
                (token_no,),
            ).fetchone()
        if row is None:
            return None
        return QueueEntry(
            token_no=row["token_no"],
            patient_name=row["patient_name"],
            age=row["age"],
            gender=row["gender"],
            phone=row["phone"],
            doctor_name=row["doctor_name"],
            department=row["department"],
            room_no=row["room_no"],
            appointment_date=row["appointment_date"],
            appointment_time=row["appointment_time"],
            token_time=row["token_time"],
            status=row["status"],
            notes=row["notes"],
        )

    def get_dashboard_counts(self) -> tuple[int, int, int, int]:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    SUM(CASE WHEN appointment_date = date('now', 'localtime')
                        THEN 1 ELSE 0 END) AS today,
                    SUM(CASE WHEN status = 'Waiting' THEN 1 ELSE 0 END) AS waiting,
                    SUM(CASE WHEN status = 'In Consultation'
                        THEN 1 ELSE 0 END) AS in_consultation,
                    SUM(CASE WHEN status = 'Completed'
                        THEN 1 ELSE 0 END) AS completed
                FROM appointments
                """
            ).fetchone()
        return (
            int(row["today"] or 0),
            int(row["waiting"] or 0),
            int(row["in_consultation"] or 0),
            int(row["completed"] or 0),
        )

    def get_upcoming_appointments(self) -> list[QueueEntry]:
        today = datetime.now().date().isoformat()
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT a.token_no, p.name AS patient_name, p.age, p.gender, p.phone,
                       d.doc_name AS doctor_name, d.dept AS department, d.room_no,
                       a.appointment_date, a.appointment_time, a.token_time,
                       a.status, a.notes
                FROM appointments a
                JOIN patients p ON p.patient_id = a.patient_id
                JOIN doctors d ON d.doctor_id = a.doctor_id
                WHERE a.appointment_date >= ?
                ORDER BY a.appointment_time, a.token_no
                LIMIT 12
                """,
                (today,),
            ).fetchall()
        return [self._entry_from_row(row) for row in rows]

    @staticmethod
    def _entry_from_row(row) -> QueueEntry:
        return QueueEntry(
            token_no=row["token_no"],
            patient_name=row["patient_name"],
            age=row["age"],
            gender=row["gender"],
            phone=row["phone"],
            doctor_name=row["doctor_name"],
            department=row["department"],
            room_no=row["room_no"],
            appointment_date=row["appointment_date"],
            appointment_time=row["appointment_time"],
            token_time=row["token_time"],
            status=row["status"],
            notes=row["notes"],
        )
