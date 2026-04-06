from datetime import datetime, date
import uuid
import os

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify
)
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from config import config

load_dotenv()


def init_db():
    conn = sqlite3.connect('ai_obesity_coaching.db')
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                age INTEGER NULL,
                gender TEXT NULL,
                height REAL NULL,
                weight REAL NULL,
                bmi REAL NULL,
                category TEXT NULL,
                target_status TEXT DEFAULT 'Ongoing',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                login_time TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bmi_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                height_cm REAL NOT NULL,
                weight_kg REAL NOT NULL,
                bmi_value REAL NOT NULL,
                category TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                track_date DATE NOT NULL,
                water_completed INTEGER DEFAULT 0,
                food_completed INTEGER DEFAULT 0,
                workout_completed INTEGER DEFAULT 0,
                challenge_completed INTEGER DEFAULT 0,
                progress_percent INTEGER DEFAULT 0,
                UNIQUE(user_id, track_date)
            )
        """)
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["JSON_SORT_KEYS"] = False

    init_db()

    def get_db_connection():
        conn = sqlite3.connect('ai_obesity_coaching.db')
        conn.row_factory = sqlite3.Row
        return conn

    # -----------------------------
    # Routes (SIMPLE TEST ROUTE)
    # -----------------------------
    @app.route("/")
    def home():
        return "Your AI Health Coach App is running 🚀"

    return app


app = create_app()

# 👇 LOCAL RUN ONLY (Render ignores this)
if __name__ == "__main__":
    app.run(debug=True)
