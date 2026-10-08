from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import sqlite3
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
DB_PATH = DATA_DIR / "historia.db"

app = Flask(__name__)
app.secret_key = "historia-clinica-local"

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_no TEXT UNIQUE,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        birth_date TEXT,
        sex TEXT,
        phone TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    );
    """)
    conn.commit()
    conn.close()

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    conn = db()
    if q:
        like = f"%{q}%"
        patients = conn.execute("""
            SELECT * FROM patients
            WHERE patient_no LIKE ?
               OR first_name LIKE ?
               OR last_name LIKE ?
               OR phone LIKE ?
            ORDER BY last_name, first_name
        """, (like, like, like, like)).fetchall()
    else:
        patients = conn.execute("""
            SELECT * FROM patients
            ORDER BY id DESC
            LIMIT 20
        """).fetchall()
    conn.close()
    return render_template("index.html", patients=patients, q=q)

@app.post("/patients")
def create_patient():
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    birth_date = request.form.get("birth_date", "").strip()
    sex = request.form.get("sex", "").strip()
    phone = request.form.get("phone", "").strip()

    if not first_name or not last_name:
        flash("Nombre y apellidos son obligatorios.")
        return redirect(url_for("index"))

    conn = db()
    cur = conn.execute("""
        INSERT INTO patients
        (patient_no, first_name, last_name, birth_date, sex, phone, created_at)
        VALUES (NULL, ?, ?, ?, ?, ?, ?)
    """, (
        first_name, last_name, birth_date or None, sex or None, phone or None,
        datetime.now().isoformat(timespec="seconds")
    ))

    patient_id = cur.lastrowid
    patient_no = f"PAC-{patient_id:06d}"
    conn.execute("UPDATE patients SET patient_no=? WHERE id=?", (patient_no, patient_id))
    conn.commit()
    conn.close()

    flash(f"Paciente creado: {patient_no}")
    return redirect(url_for("patient_detail", patient_id=patient_id))

@app.route("/patients/<int:patient_id>")
def patient_detail(patient_id):
    conn = db()
    patient = conn.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
    reports = conn.execute("""
        SELECT * FROM reports
        WHERE patient_id=?
        ORDER BY id DESC
    """, (patient_id,)).fetchall()
    conn.close()

    if patient is None:
        return "Paciente no encontrado", 404

    return render_template("patient.html", patient=patient, reports=reports)

@app.post("/patients/<int:patient_id>/report")
def create_report(patient_id):
    conn = db()
    patient = conn.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()

    if patient is None:
        conn.close()
        return "Paciente no encontrado", 404

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{patient['patient_no']}_REPORTE_{stamp}.pdf"
    path = REPORTS_DIR / file_name

    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 70

    c.setFont("Helvetica-Bold", 18)
    c.drawString(60, y, "HISTORIA CLINICA")
    y -= 35

    c.setFont("Helvetica", 11)
    lines = [
        f"Paciente No.: {patient['patient_no']}",
        f"Nombre: {patient['first_name']} {patient['last_name']}",
        f"Fecha de nacimiento: {patient['birth_date'] or ''}",
        f"Sexo: {patient['sex'] or ''}",
        f"Telefono: {patient['phone'] or ''}",
        f"Fecha del reporte: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    ]

    for line in lines:
        c.drawString(60, y, line)
        y -= 22

    y -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(60, y, "Observaciones:")
    y -= 25
    c.setFont("Helvetica", 10)
    c.drawString(60, y, "Reporte inicial v0.1.")
    c.save()

    conn.execute("""
        INSERT INTO reports (patient_id, file_name, created_at)
        VALUES (?, ?, ?)
    """, (patient_id, file_name, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()

    flash("Reporte PDF creado.")
    return redirect(url_for("patient_detail", patient_id=patient_id))

@app.route("/reports/<path:file_name>")
def open_report(file_name):
    return send_from_directory(REPORTS_DIR, file_name)

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)
