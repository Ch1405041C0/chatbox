import os
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
DB_PATH = os.getenv("DB_PATH", "chatbox.db")

QUESTIONS = {
    "vehicle": "¿Qué vehículo te interesa?",
    "buyer": "¿La unidad sería para vos? Respondé: personal, tercero o reventa.",
    "transfer": "¿A nombre de quién se realizaría la transferencia? Respondé: mi nombre, otra persona o no transferir.",
    "accept_transfer": "Para retirar la unidad es obligatorio realizar la transferencia. ¿Estás de acuerdo? Respondé sí o no.",
    "payment": "¿Cómo sería la compra? Respondé: contado, financiación o entrego usado.",
    "name": "Perfecto. ¿Cuál es tu nombre y apellido?",
}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT UNIQUE NOT NULL,
            name TEXT, vehicle TEXT, buyer_type TEXT, transfer_to TEXT,
            accepts_transfer INTEGER, payment TEXT, score INTEGER DEFAULT 50,
            status TEXT DEFAULT 'IN_PROGRESS', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
            sender TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL)""")

def normalize(text): return (text or "").strip().lower()

def add_message(session_id, sender, message):
    with db() as conn:
        conn.execute("INSERT INTO messages(session_id,sender,message,created_at) VALUES(?,?,?,?)",
                     (session_id, sender, message, datetime.utcnow().isoformat()))

def score_lead(lead):
    score = 50
    buyer, transfer, payment = normalize(lead.get("buyer_type")), normalize(lead.get("transfer_to")), normalize(lead.get("payment"))
    if "personal" in buyer: score += 20
    if "reventa" in buyer or "revendedor" in buyer: score -= 50
    if "mi nombre" in transfer: score += 20
    if "otra" in transfer or "tercero" in transfer: score -= 10
    if "no transfer" in transfer: score -= 60
    if lead.get("accepts_transfer") == 1: score += 20
    elif lead.get("accepts_transfer") == 0: score -= 80
    if "contado" in payment: score += 5
    return max(0, min(100, score))

def get_lead(session_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM leads WHERE session_id=?", (session_id,)).fetchone()
    return dict(row) if row else None

def save(session_id, **fields):
    now = datetime.utcnow().isoformat()
    with db() as conn:
        exists = conn.execute("SELECT id FROM leads WHERE session_id=?", (session_id,)).fetchone()
        if not exists:
            conn.execute("INSERT INTO leads(session_id,created_at,updated_at) VALUES(?,?,?)", (session_id,now,now))
        if fields:
            fields["updated_at"] = now
            clause = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE leads SET {clause} WHERE session_id=?", (*fields.values(),session_id))

def next_step(lead):
    if not lead.get("vehicle"): return "vehicle"
    if not lead.get("buyer_type"): return "buyer"
    if not lead.get("transfer_to"): return "transfer"
    if lead.get("accepts_transfer") is None: return "accept_transfer"
    if lead.get("accepts_transfer") == 0: return "rejected"
    if not lead.get("payment"): return "payment"
    if not lead.get("name"): return "name"
    return "complete"

def response(session_id, reply, status="IN_PROGRESS", score=None):
    add_message(session_id, "bot", reply)
    data = {"reply": reply, "status": status}
    if score is not None: data["score"] = score
    return data

def process_message(session_id, message):
    lead = get_lead(session_id)
    if not lead:
        save(session_id)
        reply = "¡Hola! 👋 Soy el asistente de ventas. Te voy a hacer unas preguntas rápidas para ayudarte con tu consulta.\n\n" + QUESTIONS["vehicle"]
        return response(session_id, reply)

    add_message(session_id, "customer", message)
    step, text = next_step(lead), normalize(message)
    if step == "vehicle": save(session_id, vehicle=message.strip())
    elif step == "buyer": save(session_id, buyer_type=message.strip())
    elif step == "transfer": save(session_id, transfer_to=message.strip())
    elif step == "accept_transfer":
        yes = text in {"si","sí","s","yes"} or text.startswith("si ") or text.startswith("sí ")
        no = text in {"no","n"} or text.startswith("no ")
        if not yes and not no: return response(session_id,"Necesito confirmar este punto. ¿Aceptás realizar la transferencia? Respondé sí o no.")
        save(session_id, accepts_transfer=1 if yes else 0)
    elif step == "payment": save(session_id, payment=message.strip())
    elif step == "name": save(session_id, name=message.strip())

    lead = get_lead(session_id); score = score_lead(lead); save(session_id, score=score)
    lead = get_lead(session_id); step = next_step(lead)
    if step == "rejected":
        save(session_id,status="REJECTED")
        return response(session_id,"Gracias por tu consulta. Actualmente las unidades se comercializan únicamente realizando la transferencia correspondiente, por lo que no podemos continuar con esta operación.","REJECTED",score)
    if step == "complete":
        status = "QUALIFIED" if score >= 60 else "REVIEW"; save(session_id,status=status)
        msg = "¡Gracias! Ya tengo los datos necesarios. " + ("Un asesor comercial continuará con tu consulta." if status=="QUALIFIED" else "Vamos a revisar tu consulta antes de derivarla a un asesor.")
        return response(session_id,msg,status,score)
    return response(session_id,QUESTIONS[step],"IN_PROGRESS",score)

@app.route("/")
def home(): return render_template("index.html")

@app.route("/asesor")
def advisor(): return render_template("advisor.html")

@app.post("/api/chat")
def chat():
    p=request.get_json(force=True); return jsonify(process_message(str(p.get("session_id","demo")),str(p.get("message",""))))

@app.get("/api/leads")
def leads():
    with db() as conn: rows=conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.get("/api/leads/<session_id>/messages")
def lead_messages(session_id):
    with db() as conn: rows=conn.execute("SELECT sender,message,created_at FROM messages WHERE session_id=? ORDER BY id",(session_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.post("/api/reset/<session_id>")
def reset(session_id):
    with db() as conn:
        conn.execute("DELETE FROM messages WHERE session_id=?",(session_id,)); conn.execute("DELETE FROM leads WHERE session_id=?",(session_id,))
    return jsonify({"ok":True})

if __name__ == "__main__":
    init_db(); app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)),debug=True)
