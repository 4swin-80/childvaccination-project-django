# Child Vaccination Management System

A Django web application for managing child vaccination records, appointments, reminders, and hospital workflows.

## Features

- Parent, hospital, and admin user roles
- Child profile management
- Vaccine scheduling based on age
- Appointment booking and status tracking
- Vaccination completion tracking
- Reminder generation for upcoming vaccines and appointments
- Hospital approval flow managed by admin

## Tech Stack

- Python 3.13
- Django 6
- SQLite
- Pillow
- python-dotenv

## Project Structure

```text
Child_Vacc_project/
|-- childvacc/
|   |-- manage.py
|   |-- childvacc/
|   |-- core/
|   `-- .env
|-- env/
|-- requirements.txt
|-- README.md
`-- LICENSE
```

## Setup

1. Create and activate a virtual environment if needed, or use the existing `env`.
2. Install dependencies:

```powershell
env\Scripts\python.exe -m pip install -r requirements.txt
```

3. Review environment variables in `childvacc/.env`.
4. Apply migrations:

```powershell
cd childvacc
..\env\Scripts\python.exe manage.py migrate
```

5. Start the development server:

```powershell
..\env\Scripts\python.exe manage.py runserver
```

6. Open `http://127.0.0.1:8000/`.

## Environment Variables

The project reads configuration from `childvacc/.env`.

```env
SECRET_KEY=replace-this-with-a-secure-secret-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
```

## Notes for GitHub

- Do not commit the `env/` virtual environment folder.
- Replace the sample `SECRET_KEY` before deploying.
- The default database is SQLite and will be created in `childvacc/db.sqlite3`.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
