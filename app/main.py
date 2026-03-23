import os
import ssl
import time
from flask import Flask, request, jsonify
from database import init_db, db
from models import Patient
from auth import require_role

app = Flask(__name__)

# ─── Routes ───────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Secure Patient Records API"}), 200


@app.route("/patient", methods=["POST"])
@require_role("editor")
def create_patient():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body provided"}), 400

    name      = data.get("name")
    age       = data.get("age")
    diagnosis = data.get("diagnosis")

    if not all([name, age, diagnosis]):
        return jsonify({"error": "name, age, and diagnosis are required"}), 400

    patient = Patient()
    patient.set_data(str(name), str(age), str(diagnosis))

    db.session.add(patient)
    db.session.commit()

    return jsonify({
        "message": "Patient created successfully",
        "id": patient.id
    }), 201


@app.route("/patient/<int:patient_id>", methods=["GET"])
@require_role("viewer", "editor")
def get_patient(patient_id):
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({"error": f"Patient {patient_id} not found"}), 404
    return jsonify(patient.get_data()), 200


@app.route("/patients", methods=["GET"])
@require_role("viewer", "editor")
def get_all_patients():
    patients = Patient.query.all()
    return jsonify([p.get_data() for p in patients]), 200


# ─── DB init with retry ───────────────────────────────────

def init_db_with_retry(app, retries=10, delay=5):
    """Retry DB connection until MySQL is ready."""
    for attempt in range(1, retries + 1):
        try:
            print(f"⏳ Attempting DB connection ({attempt}/{retries})...")
            init_db(app)
            print("✅ Database connected and tables created.")
            return
        except Exception as e:
            print(f"❌ DB not ready yet: {e}")
            if attempt < retries:
                print(f"   Retrying in {delay}s...")
                time.sleep(delay)
            else:
                print("💀 Could not connect to DB after all retries. Exiting.")
                raise


# ─── Entry Point ──────────────────────────────────────────

if __name__ == "__main__":
    init_db_with_retry(app)

    cert = os.path.join("certs", "cert.pem")
    key  = os.path.join("certs", "key.pem")

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=cert, keyfile=key)

    print("🚀 Starting Secure Patient Records API on https://0.0.0.0:8443")
    app.run(
        host="0.0.0.0",
        port=8443,
        ssl_context=ssl_context,
        debug=False
    )