from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3, json, datetime
import numpy as np

app = Flask(__name__)
app.secret_key = 'demo_secret'
DB = 'waste.db'

# ------------------- DATABASE SETUP -------------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS Institutions (
        inst_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS Locations (
        location_id INTEGER PRIMARY KEY AUTOINCREMENT,
        inst_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        FOREIGN KEY (inst_id) REFERENCES Institutions(inst_id) ON DELETE CASCADE
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS Waste_Records (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        location_id INTEGER NOT NULL,
        plastic_kg REAL NOT NULL CHECK(plastic_kg >= 0),
        organic_kg REAL NOT NULL CHECK(organic_kg >= 0),
        record_date DATE NOT NULL,
        FOREIGN KEY (location_id) REFERENCES Locations(location_id) ON DELETE CASCADE
    )""")
    conn.commit()
    conn.close()

@app.before_request
def before_request():
    init_db()

# ------------------- ROUTES -------------------

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['username'] = request.form.get('username', '')
        flash('Login successful', 'success')
        return redirect(url_for('institution'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/institution', methods=['GET', 'POST'])
def institution():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor()
    if request.method == 'POST':
        inst_name = request.form.get('inst_name', '').strip()
        if inst_name:
            cur.execute("INSERT OR IGNORE INTO Institutions(name) VALUES (?)", (inst_name,))
            conn.commit()
            cur.execute("SELECT inst_id FROM Institutions WHERE name=?", (inst_name,))
            inst = cur.fetchone()
            if inst:
                inst_id = inst['inst_id']
                for loc in ["Admin Block", "Hostel", "Canteen"]:
                    cur.execute("INSERT OR IGNORE INTO Locations(inst_id, name) VALUES (?, ?)", (inst_id, loc))
                conn.commit()
            session['inst_name'] = inst_name
            flash(f"Institution {inst_name} selected", 'success')
            return redirect(url_for('waste_entry'))
    cur.execute("SELECT * FROM Institutions ORDER BY name")
    insts = cur.fetchall()
    conn.close()
    return render_template('institution.html', institutions=insts)

@app.route('/waste-entry', methods=['GET', 'POST'])
def waste_entry():
    if 'username' not in session:
        return redirect(url_for('login'))
    inst_name = session.get('inst_name')
    if not inst_name:
        return redirect(url_for('institution'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT inst_id FROM Institutions WHERE name=?", (inst_name,))
    inst = cur.fetchone()
    if not inst:
        flash("Institution not found", "danger")
        return redirect(url_for('institution'))
    inst_id = inst['inst_id']

    if request.method == 'POST':
        try:
            loc_id = int(request.form.get('location_id', 0))
            plastic = float(request.form.get('plastic_kg', 0))
            organic = float(request.form.get('organic_kg', 0))
            record_date = request.form.get('record_date')
            if not record_date:
                raise ValueError("Date required")
            if plastic < 0 or organic < 0:
                raise ValueError("Invalid quantities")
        except Exception as e:
            flash('Invalid input: ' + str(e), 'danger')
        else:
            cur.execute("""INSERT INTO Waste_Records(location_id, plastic_kg, organic_kg, record_date)
                        VALUES (?, ?, ?, ?)""", (loc_id, plastic, organic, record_date))
            conn.commit()
            flash("Record saved", "success")

    cur.execute("SELECT * FROM Locations WHERE inst_id=?", (inst_id,))
    locations = cur.fetchall()
    conn.close()
    return render_template('waste_entry.html', inst_name=inst_name, locations=locations)

# ------------------- SMART ANALYSIS -------------------

@app.route('/summary')
def summary():
    if 'username' not in session:
        return redirect(url_for('login'))
    inst_name = session.get('inst_name')
    if not inst_name:
        return redirect(url_for('institution'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT inst_id FROM Institutions WHERE name=?", (inst_name,))
    inst = cur.fetchone()
    if not inst:
        return redirect(url_for('institution'))
    inst_id = inst['inst_id']

    cur.execute("""
        SELECT record_date, SUM(plastic_kg) as plastic, SUM(organic_kg) as organic
        FROM Waste_Records wr
        JOIN Locations l ON wr.location_id = l.location_id
        WHERE l.inst_id=?
        GROUP BY record_date
        ORDER BY record_date
    """, (inst_id,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return render_template('summary.html', labels="[]", series="[]", no_data=True)

    dates = [r['record_date'] for r in rows]
    plastic_data = [r['plastic'] for r in rows]
    organic_data = [r['organic'] for r in rows]

    # AI-like trend analysis (simple linear prediction)
    if len(plastic_data) > 2:
        x = np.arange(len(plastic_data))
        plastic_trend = np.polyfit(x, plastic_data, 1)[0]
        organic_trend = np.polyfit(x, organic_data, 1)[0]
    else:
        plastic_trend = organic_trend = 0

    # Trend insights
    if plastic_trend > organic_trend:
        trend_msg = "⚠️ Plastic waste is increasing faster — urgent reduction needed!"
    elif organic_trend > plastic_trend:
        trend_msg = "✅ Organic waste is increasing faster — good composting potential!"
    else:
        trend_msg = "📊 Waste levels stable — keep monitoring regularly."

    series = [
        {'label': 'Plastic', 'data': plastic_data, 'borderColor': 'red', 'tension': 0.4},
        {'label': 'Organic', 'data': organic_data, 'borderColor': 'green', 'tension': 0.4}
    ]
    return render_template('summary.html',
                           labels=json.dumps(dates),
                           series=json.dumps(series),
                           no_data=False,
                           trend_msg=trend_msg)

@app.route('/recommendations')
def recommendations():
    if 'username' not in session:
        return redirect(url_for('login'))
    inst_name = session.get('inst_name')
    if not inst_name:
        return redirect(url_for('institution'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT SUM(plastic_kg) as plastic, SUM(organic_kg) as organic
        FROM Waste_Records wr
        JOIN Locations l ON wr.location_id = l.location_id
        JOIN Institutions i ON l.inst_id=i.inst_id
        WHERE i.name=?
    """, (inst_name,))
    row = cur.fetchone()
    conn.close()

    recs = []
    if not row or (row['plastic'] is None and row['organic'] is None):
        recs.append("No data available. Please add waste records.")
    else:
        p = row['plastic'] or 0
        o = row['organic'] or 0
        total = p + o if (p + o) > 0 else 1
        eco_score = round(100 - (p / total * 100), 2)

        # Smart recommendations based on ratio
        if eco_score < 60:
            recs.append("Plastic levels high — initiate awareness and switch to biodegradable materials.")
        elif eco_score < 80:
            recs.append("Moderate eco score — enhance composting and segregation techniques.")
        else:
            recs.append("Excellent eco score — maintain sustainable practices!")
        recs.append(f"Current Eco Score: {eco_score}%")

    return render_template("recommendations.html", inst_name=inst_name, recs=recs)

@app.route('/leaderboard')
def leaderboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT i.name AS college_name,
               ROUND(AVG(wr.plastic_kg),2) AS avg_plastic,
               ROUND(AVG(wr.organic_kg),2) AS avg_organic,
               ROUND(100 - (AVG(wr.plastic_kg)/(AVG(wr.plastic_kg)+AVG(wr.organic_kg))*100),2) AS avg_eco
        FROM Institutions i
        JOIN Locations l ON i.inst_id = l.inst_id
        JOIN Waste_Records wr ON l.location_id = wr.location_id
        GROUP BY i.inst_id
        ORDER BY avg_eco DESC
    """)
    results = cur.fetchall()
    conn.close()

    if not results:
        results = []

    return render_template("leaderboard.html", results=results)

# ------------------- MAIN -------------------
if __name__ == '__main__':
    app.run(debug=True)
