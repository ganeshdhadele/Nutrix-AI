import json
import os
import sqlite3
from pathlib import Path
from functools import wraps
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("NUTRIX_SECRET_KEY", "dev-only-change-this-secret")
DB_PATH = Path(__file__).with_name("nutrix.db")


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS meal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            meal_name TEXT NOT NULL,
            meal_type TEXT NOT NULL,
            calories REAL NOT NULL DEFAULT 0,
            protein REAL NOT NULL DEFAULT 0,
            carbs REAL NOT NULL DEFAULT 0,
            fats REAL NOT NULL DEFAULT 0,
            meal_date TEXT NOT NULL DEFAULT (date('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS weekly_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_name TEXT NOT NULL,
            plan_data TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Please log in first."}), 401
            flash("Please log in to access this feature.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def home():
    return render_template("dashboard.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter all details. Password must be at least 8 characters.")
            return redirect(url_for("register"))
        try:
            with get_db() as db:
                db.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)",
                           (name, email, generate_password_hash(password)))
            flash("Account created! Please log in.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("This email is already registered.")
            return redirect(url_for("register"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with get_db() as db:
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("home"))
        flash("Invalid email or password.")
    return render_template("login.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/meal-planner")
def meal_planner():
    return render_template("meal_planner.html")


@app.route("/nutrition")
@login_required
def nutrition():
    return render_template("nutrition.html")


@app.route("/weekly-planner")
@login_required
def weekly_planner():
    return render_template("weekly_planner.html")


@app.route("/api/meal-history", methods=["GET", "POST"])
@login_required
def meal_history():
    user_id = session["user_id"]
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        name = str(data.get("meal_name", "")).strip()
        meal_type = str(data.get("meal_type", "")).strip()
        if not name or not meal_type:
            return jsonify({"error": "Meal name and meal type are required."}), 400
        values = {}
        try:
            for field in ("calories", "protein", "carbs", "fats"):
                values[field] = float(data.get(field, 0))
                if not 0 <= values[field] <= 100000:
                    raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "Nutrition values must be valid non-negative numbers."}), 400
        with get_db() as db:
            cur = db.execute("""INSERT INTO meal_history
                (user_id,meal_name,meal_type,calories,protein,carbs,fats)
                VALUES(?,?,?,?,?,?,?)""",
                (user_id, name[:150], meal_type[:50], values["calories"],
                 values["protein"], values["carbs"], values["fats"]))
        return jsonify({"message": "Meal saved successfully.", "id": cur.lastrowid}), 201
    with get_db() as db:
        rows = db.execute("""SELECT id,meal_name,meal_type,calories,protein,carbs,fats,meal_date,created_at
            FROM meal_history WHERE user_id=? ORDER BY created_at DESC LIMIT 100""", (user_id,)).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/meal-history/<int:meal_id>", methods=["DELETE"])
@login_required
def delete_meal_history(meal_id):
    with get_db() as db:
        cur = db.execute("DELETE FROM meal_history WHERE id=? AND user_id=?",
                         (meal_id, session["user_id"]))
    if not cur.rowcount:
        return jsonify({"error": "Meal not found."}), 404
    return jsonify({"message": "Meal deleted."})


@app.route("/api/weekly-plans", methods=["GET", "POST"])
@login_required
def weekly_plans():
    user_id = session["user_id"]
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        name, plan = str(data.get("plan_name", "")).strip(), data.get("plan_data")
        if not name or not isinstance(plan, (dict, list)):
            return jsonify({"error": "Provide a plan name and plan data."}), 400
        with get_db() as db:
            cur = db.execute("INSERT INTO weekly_plans(user_id,plan_name,plan_data) VALUES(?,?,?)",
                             (user_id, name[:100], json.dumps(plan, ensure_ascii=False)))
        return jsonify({"message": "Weekly plan saved.", "id": cur.lastrowid}), 201
    with get_db() as db:
        rows = db.execute("SELECT id,plan_name,plan_data,created_at FROM weekly_plans WHERE user_id=? ORDER BY created_at DESC",
                          (user_id,)).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/recommendations", methods=["POST"])
def recommendations():
    data = request.get_json(silent=True) or {}
    food_type = data.get("foodType", "veg")
    meal_time = data.get("mealTime", "lunch")
    goal = data.get("goal", "balanced")
    allergies = [x.strip().lower() for x in str(data.get("allergy", "")).split(",") if x.strip()]
    meals = {
      "breakfast": {
        "veg": [("Poha with Peanuts","Poha with lemon and herbs; omit peanuts if needed."),
                ("Vegetable Upma","Semolina with vegetables."),("Besan Chilla","Chickpea-flour pancakes.")],
        "egg": [("Egg and Toast","Fully cooked eggs with toast."),("Egg Poha","Poha with fully cooked egg.")],
        "nonveg": [("Egg and Toast","Fully cooked eggs with toast."),("Chicken Sandwich","Sandwich with fully cooked chicken.")]},
      "lunch": {
        "veg": [("Dal and Rice","Lentils with rice."),("Chana Rice Bowl","Chickpeas with rice."),("Paneer Rice Bowl","Paneer with rice.")],
        "egg": [("Egg Curry and Rice","Egg curry with rice."),("Dal, Rice and Egg","Dal, rice and fully cooked egg.")],
        "nonveg": [("Chicken and Rice","Fully cooked chicken with rice."),("Fish and Rice","Fully cooked fish with rice.")]},
      "snack": {
        "veg": [("Roasted Chana","Roasted chickpeas."),("Fruit and Curd","Fruit with plain curd if suitable."),("Peanut Chaat","Peanuts with lemon; avoid if allergic.")],
        "egg": [("Boiled Egg","Fully cooked egg with fruit."),("Roasted Chana","Roasted chickpeas.")],
        "nonveg": [("Egg Snack","Fully cooked egg with fruit."),("Chicken Sandwich","Sandwich with fully cooked chicken.")]},
      "dinner": {
        "veg": [("Dal Khichdi","Rice and lentils cooked together."),("Paneer Rice Bowl","Paneer with rice."),("Chana Pulao","Chickpeas and rice.")],
        "egg": [("Egg Bhurji and Rice","Fully cooked egg with rice."),("Dal Rice and Egg","Dal, rice and fully cooked egg.")],
        "nonveg": [("Chicken Rice Bowl","Fully cooked chicken with rice."),("Fish and Rice","Fully cooked fish with rice.")]}
    }
    if food_type not in ("veg","egg","nonveg") or meal_time not in ("breakfast","lunch","snack","dinner"):
        return jsonify({"error":"Choose valid meal preferences."}), 400
    suggestions = meals[meal_time][food_type]
    result = [{"name": n, "description": d} for n,d in suggestions
              if not any(a in (n+" "+d).lower() for a in allergies)]
    notes = {"balanced":"Choose a variety of foods across the day.",
             "protein":"Options may include lentils, chickpeas, paneer, eggs or fully cooked meat.",
             "energy":"Choose a satisfying meal and drink water regularly."}
    return jsonify({"ideas":result, "note":notes.get(goal,notes["balanced"]),
                    "type":"rule-based recommendations"})


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
