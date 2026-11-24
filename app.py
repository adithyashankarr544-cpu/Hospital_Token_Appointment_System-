"""Start the Hospital Outpatient Token & Appointment System."""

import logging
import sqlite3
import tkinter as tk
from tkinter import messagebox

from hospital_app.database import Database
from hospital_app.ui.main_window import MainWindow


def main() -> None:
    root = tk.Tk()
    try:
        database = Database()
        database.initialize()
    except (OSError, sqlite3.Error) as error:
        messagebox.showerror(
            "Startup error",
            f"The application database could not be initialized.\n\n{error}",
            parent=root,
        )
        root.destroy()
        return

    try:
        MainWindow(root, database)
        root.mainloop()
    except Exception as error:
        logging.exception("The hospital application could not start")
        messagebox.showerror(
            "Application error",
            f"The application could not start.\n\n{error}",
            parent=root,
        )
        root.destroy()


if __name__ == "__main__":
    main()
