# Hospital Outpatient Token & Appointment System

A local Windows desktop application for hospital reception staff to manage
patients, doctors, appointment schedules, outpatient tokens, and consultation
queues. It is built with Python, Tkinter/ttk, and SQLite and is suitable as a
beginner-friendly MCA III Semester mini-project.

## Problem statement

Outpatient reception desks need to keep patient details, doctor availability,
appointment times, and queue status organized. Paper-based records can be hard
to search and may lead to duplicate bookings or missed patients. This project
keeps that information in a local relational database and offers one desktop
interface for managing it.

## Objectives

- Register and search patient records, then update them safely.
- Maintain doctor details and prevent accidental deletion of doctors in use.
- Schedule appointments for existing patients and generate unique token IDs.
- Prevent a doctor from receiving two active appointments at the same time.
- Manage doctor queues using clear waiting, consultation, completed, and
  cancelled statuses.
- Show live counts and appointment information from SQLite.
- Preserve existing data when the database schema changes.

## Features

- Six working sidebar pages: Dashboard, Patient Management, Doctor Management,
  Book Appointment, Live Token Queue, and Appointment History.
- Dashboard counts for patients, doctors, today's appointments, waiting
  patients, in-consultation patients, and completed consultations.
- Dashboard overview of today's/upcoming appointments and recent patients.
- Patient search by name or phone, with edit and safe delete operations.
- Doctor search and add/edit/delete operations.
- Appointment booking with registered-patient and doctor selectors, fee,
  department, room, date, time, notes, and generated token confirmation.
- Live queue filters for doctor and status, search by token or name, details,
  Call Next, Mark Done, and Cancel Appointment.
- Appointment history search by token, patient, or doctor, plus date/status
  filters and note editing.
- Parameterized SQL, transaction-managed connections, and SQLite foreign keys.
- Sample doctors are inserted only when the same doctor and department are not
  already present.
- On the first launch after this update, records from the older `hospital.db`
  are copied into `hospital_management.db`; existing records are retained and
  old `Called`/`Done` statuses are migrated to `In Consultation`/`Completed`.
  A migration marker prevents importing the old database twice.

## Technologies and requirements

- Windows 10/11
- Python 3.10 or later (the project has been tested with the supplied Python
  3.14 virtual environment)
- Tkinter and SQLite, included with the standard Python installation
- VS Code (optional, recommended)
- No web server, external database, or third-party package is required.

## Database schema

`hospital_management.db` is created alongside `app.py`.

- `doctors`: `doctor_id`, `doc_name`, `dept`, `fee`, and `room_no`.
- `patients`: `patient_id`, `name`, `age`, `phone`, optional `blood_group`, and
  `gender`.
- `appointments`: `token_no`, doctor/patient foreign keys, `appointment_date`,
  `appointment_time`, booking `token_time`, `status`, and `notes`.
- `schema_migrations`: records completed non-destructive migrations and legacy
  database imports.

Indexes support patient lookups and doctor queue ordering. Appointment booking
checks for a doctor/time conflict inside a write transaction. Patient and
doctor records referenced by appointments cannot be deleted.

## System workflow

1. Register a patient in **Patient Management**.
2. Open **Book Appointment**, select the patient and doctor, then enter a
   future date and time.
3. Select **GENERATE TOKEN & BOOK APPOINTMENT**. The app validates the booking,
   saves it, and shows its token and appointment information.
4. Reception staff use **Live Token Queue** to filter a doctor queue and call
   the next waiting appointment.
5. After the consultation, select **MARK DONE**. A waiting appointment may
   instead be cancelled.
6. **Appointment History** can search and filter appointments, including
   completed and cancelled records.

## Installation

1. Open this project folder in VS Code.
2. Use the included `.venv` if it is available. If not, install Python and
   confirm Tkinter is included in that installation.
3. No `pip install` step is needed; the application uses Python standard
   library modules only.
4. On the first run, the app creates or safely migrates
   `hospital_management.db`. Before the migration, timestamped SQLite backups
   are kept in `backups/`.

## Run the application

In PowerShell, first change to the project folder (adjust the folder if you
saved the project elsewhere):

```powershell
Set-Location "F:\Adi\python mini proj"
.\.venv\Scripts\python.exe app.py
```

In VS Code, open the project folder and use **Terminal → Run Task → Run
Hospital Appointment System**. The workspace also offers this task on folder
open if you allow VS Code automatic tasks.

## Run tests

Tests use temporary databases and do not alter the project's patient records:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Python files explained

- `app.py` starts Tkinter, initializes SQLite, and reports startup errors.
- `hospital_app/database.py` creates the database, safely migrates old table
  layouts, imports the previous database once, and seeds sample doctors.
- `hospital_app/models.py` defines small typed data records shared by the
  database and screens.
- `hospital_app/repositories/patient_repository.py` contains patient SQL.
- `hospital_app/repositories/doctor_repository.py` contains doctor SQL.
- `hospital_app/repositories/appointment_repository.py` contains appointment,
  queue, search, history, and dashboard SQL.
- `hospital_app/services/appointment_service.py` validates input and applies
  appointment and doctor business rules.
- `hospital_app/ui/main_window.py` builds the sidebar and connects pages to the
  service and repositories.
- `hospital_app/ui/dashboard_view.py` displays database-backed dashboard
  statistics and summaries.
- `hospital_app/ui/patient_form.py` provides patient registration, search,
  update, and deletion controls.
- `hospital_app/ui/doctor_form.py` provides doctor administration.
- `hospital_app/ui/appointment_form.py` provides the appointment booking form
  and token-generation action.
- `hospital_app/ui/queue_view.py` provides doctor/status filters and live queue
  actions.
- `hospital_app/ui/history_view.py` provides appointment history search,
  filtering, and note editing.
- `tests/test_workflows.py` verifies database migration, validation, CRUD,
  booking, token handling, queue transitions, and persistence with temporary
  databases.
- `.vscode/tasks.json` defines the optional VS Code run task.

## Future enhancements

- Add login roles for reception staff and clinicians.
- Add token printing, appointment reminders, and audit history.
- Add database export and scheduled backup controls inside the application.
- Add paging for very large patient and appointment tables.
