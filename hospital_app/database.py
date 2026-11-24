"""SQLite connection management, safe migrations, and sample data."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator


SAMPLE_DOCTORS = (
    ("Dr. Arun", "General Medicine", 500.00, "101"),
    ("Dr. Priya", "Pediatrics", 600.00, "102"),
    ("Dr. Kumar", "Orthopedics", 800.00, "201"),
    ("Dr. Sneha", "Dermatology", 700.00, "202"),
    ("Dr. Ravi", "Cardiology", 900.00, "301"),
)


class Database:
    """Owns SQLite connections and applies non-destructive schema migrations."""

    def __init__(
        self,
        database_path: str | Path | None = None,
        legacy_database_path: str | Path | None = None,
    ) -> None:
        default_path = Path(__file__).resolve().parent.parent / "hospital_management.db"
        self.database_path = Path(database_path) if database_path else default_path
        self.legacy_database_path = (
            Path(legacy_database_path)
            if legacy_database_path
            else (
                self.database_path.parent / "hospital.db"
                if database_path is None
                else None
            )
        )

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield a transactional connection and always close it afterward."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            is not None
        )

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
        return {
            row["name"] for row in connection.execute(f'PRAGMA table_info("{table}")')
        }

    @staticmethod
    def _create_patients(connection: sqlite3.Connection, table: str = "patients") -> None:
        connection.execute(
            f"""
            CREATE TABLE {table} (
                patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                age INTEGER NOT NULL CHECK (age BETWEEN 1 AND 120),
                phone TEXT NOT NULL CHECK (
                    length(phone) BETWEEN 7 AND 15 AND phone NOT GLOB '*[^0-9]*'
                ),
                blood_group TEXT CHECK (
                    blood_group IS NULL OR blood_group IN (
                        'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'
                    )
                ),
                gender TEXT NOT NULL CHECK (gender IN ('Female', 'Male', 'Other'))
            )
            """
        )

    @staticmethod
    def _create_appointments(
        connection: sqlite3.Connection, table: str = "appointments"
    ) -> None:
        connection.execute(
            f"""
            CREATE TABLE {table} (
                token_no INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_id INTEGER NOT NULL,
                patient_id INTEGER NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                token_time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Waiting'
                    CHECK (status IN (
                        'Waiting', 'In Consultation', 'Completed', 'Cancelled'
                    )),
                notes TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
                    ON UPDATE CASCADE ON DELETE RESTRICT,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
                    ON UPDATE CASCADE ON DELETE RESTRICT
            )
            """
        )

    def _migrate_patients(self, connection: sqlite3.Connection) -> None:
        if not self._table_exists(connection, "patients"):
            self._create_patients(connection)
            return
        info = {
            row["name"]: row for row in connection.execute("PRAGMA table_info(patients)")
        }
        blood_group_sql = next(
            (
                row["sql"]
                for row in connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'patients'"
                )
            ),
            "",
        )
        if "blood_group" not in info:
            raise sqlite3.DatabaseError(
                "The existing patients table is missing the blood_group column."
            )
        nullable = info["blood_group"]["notnull"] == 0
        accepts_optional = "IS NULL OR" in blood_group_sql
        required_columns = {
            "patient_id",
            "name",
            "age",
            "phone",
            "blood_group",
            "gender",
        }
        if nullable and accepts_optional and required_columns.issubset(info):
            return

        connection.execute("DROP INDEX IF EXISTS idx_patients_name_phone")
        self._create_patients(connection, "patients_new")
        connection.execute(
            """
            INSERT INTO patients_new
                (patient_id, name, age, phone, blood_group, gender)
            SELECT patient_id, name, age, phone, NULLIF(blood_group, ''), gender
            FROM patients
            """
        )
        connection.execute("DROP TABLE patients")
        connection.execute("ALTER TABLE patients_new RENAME TO patients")

    def _migrate_appointments(self, connection: sqlite3.Connection) -> None:
        if not self._table_exists(connection, "appointments"):
            self._create_appointments(connection)
            return
        columns = self._columns(connection, "appointments")
        sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'appointments'"
        ).fetchone()["sql"]
        required_columns = {
            "token_no",
            "doctor_id",
            "patient_id",
            "appointment_date",
            "appointment_time",
            "token_time",
            "status",
            "notes",
        }
        if required_columns.issubset(columns) and "In Consultation" in sql:
            return
        if not {"token_no", "doctor_id", "patient_id", "token_time", "status"}.issubset(
            columns
        ):
            raise sqlite3.DatabaseError(
                "The existing appointments table has an unsupported schema."
            )

        date_expression = (
            "appointment_date"
            if "appointment_date" in columns
            else "substr(token_time, 1, 10)"
        )
        time_expression = (
            "appointment_time"
            if "appointment_time" in columns
            else "substr(token_time, 12, 5)"
        )
        notes_expression = "COALESCE(notes, '')" if "notes" in columns else "''"
        connection.execute("DROP INDEX IF EXISTS idx_appointments_doctor_queue")
        self._create_appointments(connection, "appointments_new")
        connection.execute(
            f"""
            INSERT INTO appointments_new (
                token_no, doctor_id, patient_id, appointment_date,
                appointment_time, token_time, status, notes
            )
            SELECT token_no, doctor_id, patient_id, {date_expression},
                   {time_expression}, token_time,
                   CASE status
                       WHEN 'Called' THEN 'In Consultation'
                       WHEN 'Done' THEN 'Completed'
                       ELSE status
                   END,
                   {notes_expression}
            FROM appointments
            """
        )
        connection.execute("DROP TABLE appointments")
        connection.execute("ALTER TABLE appointments_new RENAME TO appointments")

    @staticmethod
    def _doctor_id(
        connection: sqlite3.Connection, doctor_row: sqlite3.Row
    ) -> int:
        found = connection.execute(
            "SELECT doctor_id FROM doctors WHERE doc_name = ? AND dept = ?",
            (doctor_row["doc_name"], doctor_row["dept"]),
        ).fetchone()
        if found:
            return int(found["doctor_id"])
        cursor = connection.execute(
            """
            INSERT INTO doctors (doc_name, dept, fee, room_no)
            VALUES (?, ?, ?, ?)
            """,
            (
                doctor_row["doc_name"],
                doctor_row["dept"],
                doctor_row["fee"],
                doctor_row["room_no"],
            ),
        )
        return int(cursor.lastrowid)

    def _import_legacy_database(self, connection: sqlite3.Connection) -> None:
        source_path = self.legacy_database_path
        if (
            source_path is None
            or source_path.resolve() == self.database_path.resolve()
            or not source_path.exists()
        ):
            return
        migration_key = f"legacy-import:{source_path.resolve()}"
        if connection.execute(
            "SELECT 1 FROM schema_migrations WHERE migration_key = ?",
            (migration_key,),
        ).fetchone():
            return

        source = sqlite3.connect(f"file:{source_path.resolve().as_posix()}?mode=ro", uri=True)
        source.row_factory = sqlite3.Row
        try:
            source_tables = {
                row["name"]
                for row in source.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            if not {"doctors", "patients", "appointments"}.issubset(source_tables):
                raise sqlite3.DatabaseError(
                    f"Legacy database {source_path.name} is missing expected tables."
                )
            doctor_columns = self._columns(source, "doctors")
            patient_columns = self._columns(source, "patients")
            appointment_columns = self._columns(source, "appointments")
            if not {
                "doctor_id", "doc_name", "dept", "fee", "room_no"
            }.issubset(doctor_columns) or not {
                "patient_id", "name", "age", "phone", "gender"
            }.issubset(patient_columns) or not {
                "token_no", "doctor_id", "patient_id", "token_time", "status"
            }.issubset(appointment_columns):
                raise sqlite3.DatabaseError(
                    f"Legacy database {source_path.name} has an unsupported schema."
                )

            doctor_ids = {
                row["doctor_id"]: self._doctor_id(connection, row)
                for row in source.execute("SELECT * FROM doctors")
            }
            patient_ids: dict[int, int] = {}
            for row in source.execute("SELECT * FROM patients"):
                found = connection.execute(
                    """
                    SELECT patient_id FROM patients
                    WHERE lower(name) = lower(?) AND phone = ?
                    """,
                    (row["name"], row["phone"]),
                ).fetchone()
                if found:
                    patient_ids[row["patient_id"]] = int(found["patient_id"])
                    continue
                blood_group = row["blood_group"] if "blood_group" in patient_columns else None
                cursor = connection.execute(
                    """
                    INSERT INTO patients (name, age, phone, blood_group, gender)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        row["name"],
                        row["age"],
                        row["phone"],
                        blood_group or None,
                        row["gender"],
                    ),
                )
                patient_ids[row["patient_id"]] = int(cursor.lastrowid)

            for row in source.execute("SELECT * FROM appointments"):
                legacy_time = row["token_time"]
                appointment_date = (
                    row["appointment_date"]
                    if "appointment_date" in appointment_columns
                    else legacy_time[:10]
                )
                appointment_time = (
                    row["appointment_time"]
                    if "appointment_time" in appointment_columns
                    else legacy_time[11:16]
                )
                if not appointment_date or not appointment_time:
                    parsed = datetime.fromisoformat(legacy_time)
                    appointment_date = parsed.date().isoformat()
                    appointment_time = parsed.strftime("%H:%M")
                status = {
                    "Called": "In Consultation",
                    "Done": "Completed",
                }.get(row["status"], row["status"])
                if status not in {
                    "Waiting",
                    "In Consultation",
                    "Completed",
                    "Cancelled",
                }:
                    status = "Waiting"
                notes = row["notes"] if "notes" in appointment_columns else ""
                values = (
                    doctor_ids[row["doctor_id"]],
                    patient_ids[row["patient_id"]],
                    appointment_date,
                    appointment_time,
                    legacy_time,
                    status,
                    notes or "",
                )
                token_exists = connection.execute(
                    "SELECT 1 FROM appointments WHERE token_no = ?",
                    (row["token_no"],),
                ).fetchone()
                if token_exists is None:
                    connection.execute(
                        """
                        INSERT INTO appointments (
                            token_no, doctor_id, patient_id, appointment_date,
                            appointment_time, token_time, status, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (row["token_no"], *values),
                    )
                else:
                    connection.execute(
                        """
                        INSERT INTO appointments (
                            doctor_id, patient_id, appointment_date,
                            appointment_time, token_time, status, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        values,
                    )
        finally:
            source.close()
        connection.execute(
            "INSERT INTO schema_migrations (migration_key) VALUES (?)",
            (migration_key,),
        )

    def initialize(self) -> None:
        """Create tables, migrate old layouts, seed doctors, and import old data."""
        with self.connect() as connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS doctors (
                    doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_name TEXT NOT NULL CHECK (length(trim(doc_name)) > 0),
                    dept TEXT NOT NULL CHECK (length(trim(dept)) > 0),
                    fee REAL NOT NULL CHECK (fee >= 0),
                    room_no TEXT NOT NULL CHECK (length(trim(room_no)) > 0),
                    UNIQUE (doc_name, dept)
                )
                """
            )
            self._migrate_patients(connection)
            self._migrate_appointments(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    migration_key TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_name_phone
                ON patients(lower(name), phone)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_appointments_doctor_queue
                ON appointments(doctor_id, status, appointment_date, appointment_time)
                """
            )
            for doctor in SAMPLE_DOCTORS:
                connection.execute(
                    """
                    INSERT INTO doctors (doc_name, dept, fee, room_no)
                    SELECT ?, ?, ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM doctors WHERE doc_name = ? AND dept = ?
                    )
                    """,
                    (*doctor, doctor[0], doctor[1]),
                )
            self._import_legacy_database(connection)
            connection.execute("PRAGMA foreign_keys = ON")
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise sqlite3.IntegrityError(
                    f"Database migration left foreign-key violations: {violations!r}"
                )
