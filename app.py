from datetime import datetime, date
import uuid

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from config import config

load_dotenv()


def init_db():
    """Initialize database and tables."""
    conn = sqlite3.connect('ai_obesity_coaching.db')
    cursor = conn.cursor()
    try:
        # Create tables
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
                login_time TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
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
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                track_date DATE NOT NULL,
                water_completed INTEGER NOT NULL DEFAULT 0,
                food_completed INTEGER NOT NULL DEFAULT 0,
                workout_completed INTEGER NOT NULL DEFAULT 0,
                challenge_completed INTEGER NOT NULL DEFAULT 0,
                progress_percent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, track_date),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (admin_id) REFERENCES admin(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS motivational_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quote_text TEXT NOT NULL,
                author TEXT DEFAULT 'Unknown',
                used_date DATE NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_flow (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                height REAL,
                weight REAL,
                bmi REAL,
                category TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Insert sample data
        cursor.execute("""
            INSERT OR IGNORE INTO admin (email, password_hash)
            VALUES ('admin@healthcoach.com', 'scrypt:32768:8:1$PKn6wA2I5vZY9tk7$6386dce8610f76726701edf42c96ebad939881f07d55cecfb26136544665ab7cfc60ba93622508d5770421bacb9243c29320e3ee8b2ddd93ceaffb3894b61f59')
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO users (full_name, email, password_hash, target_status) VALUES
            ('John Doe', 'john@example.com', 'scrypt:32768:8:1$VqcwQQHZbdZKImHo$fc53891e1c32dbbdd21d0b8821a8ba3cc25c4cb170b8cc44648772ec1a7f7e27f4e1e3db38770bcbb65269ed78334bd51d8bb45b31efcc576e0bc33be94f6276', 'Ongoing'),
            ('Jane Smith', 'jane@example.com', 'scrypt:32768:8:1$VqcwQQHZbdZKImHo$fc53891e1c32dbbdd21d0b8821a8ba3cc25c4cb170b8cc44648772ec1a7f7e27f4e1e3db38770bcbb65269ed78334bd51d8bb45b31efcc576e0bc33be94f6276', 'Ongoing')
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO motivational_quotes (quote_text, author) VALUES
            ('The journey of a thousand miles begins with a single step.', 'Lao Tzu'),
            ('Success is the sum of small efforts, repeated day in and day out.', 'Robert Collier'),
            ('It does not matter how slowly you go as long as you do not stop.', 'Confucius'),
            ('Your body can stand almost anything. It''s your mind that you have to convince.', 'Unknown'),
            ('Discipline is the bridge between goals and accomplishment.', 'Jim Rohn')
        """)
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def create_app():
    """Application factory."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY

    # Initialize database tables if not exist
    init_db()

    # -----------------------------
    # Database helper
    # -----------------------------

    def get_db_connection():
        """Create a new SQLite connection."""
        conn = sqlite3.connect('ai_obesity_coaching.db')
        conn.row_factory = sqlite3.Row
        return conn

    # -----------------------------
    # Utility functions
    # -----------------------------

    def calculate_bmi(height_cm: float, weight_kg: float):
        """Calculate BMI and category based on height (cm) and weight (kg)."""
        if height_cm <= 0:
            return None, None
        height_m = height_cm / 100.0
        bmi = weight_kg / (height_m**2)
        bmi = round(bmi, 2)

        if bmi < 18.5:
            category = "Underweight"
        elif 18.5 <= bmi < 25:
            category = "Normal"
        elif 25 <= bmi < 30:
            category = "Overweight"
        elif 30 <= bmi < 35:
            category = "Obese"
        else:
            category = "Severely Obese"

        return bmi, category

    def classify_bmi(bmi: float):
        if bmi < 18.5:
            return "Underweight"
        if bmi < 25:
            return "Normal"
        if bmi < 30:
            return "Overweight"
        return "Obese"

    def calculate_bmr(age: int, gender: str, height: float, weight: float):
        """Calculate Basal Metabolic Rate using Mifflin-St Jeor Equation."""
        gender_value = (gender or "Other").strip().lower()
        if gender_value == "male":
            return 10 * weight + 6.25 * height - 5 * age + 5
        return 10 * weight + 6.25 * height - 5 * age - 161

    def get_user_value(user, key, default):
        if user is None:
            return default
        if hasattr(user, "get"):
            return user.get(key) or default
        value = user[key]
        return value if value is not None else default

    def generate_diet_plan(user):
        age = get_user_value(user, 'age', 30)
        gender = get_user_value(user, 'gender', 'Other')
        height = get_user_value(user, 'height', 170)
        weight = get_user_value(user, 'weight', 70)
        category = get_user_value(user, 'category', 'Normal')

        # Calculate BMR and TDEE
        bmr = calculate_bmr(age, gender, height, weight)
        # Assume sedentary activity level
        tdee = bmr * 1.2

        # Adjust calories based on category
        if category == "Underweight":
            calories = int(tdee + 500)  # Surplus for weight gain
        elif category == "Normal":
            calories = int(tdee)
        elif category == "Overweight":
            calories = int(tdee - 500)  # Deficit for weight loss
        elif category == "Obese":
            calories = int(tdee - 750)
        else:  # Severely Obese
            calories = int(tdee - 1000)

        # Ensure minimum calories
        calories = max(calories, 1200)

        # Vary meals based on user data
        import random
        breakfast_options = [
            "Oatmeal with nuts, banana, and a glass of milk.",
            "Greek yogurt with berries and seeds.",
            "Smoothie with spinach, berries, and protein.",
            "Whole grain toast with avocado and eggs.",
        ]
        lunch_options = [
            "Grilled chicken, brown rice, and salad.",
            "Turkey salad with quinoa and greens.",
            "Fish with roasted vegetables.",
            "Vegetable stir-fry with tofu.",
        ]
        dinner_options = [
            "Salmon, sweet potato, and steamed greens.",
            "Stir-fried vegetables with lean protein.",
            "Grilled fish with quinoa and salad.",
            "Chicken breast with broccoli and rice.",
        ]

        # Seed random with user-specific data for consistency
        random.seed(hash((age, gender, height, weight)))

        breakfast = random.choice(breakfast_options)
        lunch = random.choice(lunch_options)
        dinner = random.choice(dinner_options)

        advice = f"Based on your age {age}, gender {gender}, and BMI category {category}, aim for {calories} calories daily. Focus on whole foods and portion control."

        return {
            "calories": calories,
            "breakfast": breakfast,
            "lunch": lunch,
            "dinner": dinner,
            "advice": advice,
        }

    def generate_workout_plan(user):
        age = get_user_value(user, 'age', 30)
        gender = get_user_value(user, 'gender', 'Other')
        height = get_user_value(user, 'height', 170)
        weight = get_user_value(user, 'weight', 70)
        category = get_user_value(user, 'category', 'Normal')

        # Determine level based on age and category
        if age > 60 or category in ["Obese", "Severely Obese"]:
            level = "Beginner"
            duration = "20-30 minutes"
            exercises = [
                "Gentle walking",
                "Chair squats",
                "Arm circles",
                "Light stretching",
                "Breathing exercises",
            ]
        elif age > 40 or category == "Overweight":
            level = "Beginner to Intermediate"
            duration = "30-40 minutes"
            exercises = [
                "Brisk walking",
                "Seated leg raises",
                "Low-impact cycling",
                "Gentle yoga",
                "Core strengthening",
            ]
        elif category == "Underweight":
            level = "Intermediate"
            duration = "40-50 minutes"
            exercises = [
                "Bodyweight squats",
                "Push-ups",
                "Dumbbell rows",
                "Plank holds",
                "Light cardio",
            ]
        else:  # Normal
            level = "Intermediate"
            duration = "40-50 minutes"
            exercises = [
                "Jogging or brisk walk",
                "Dumbbell lunges",
                "Plank holds",
                "Core exercises",
                "Full body strength",
            ]

        # Vary exercises based on user data
        import random
        random.seed(hash((age, gender, height, weight)))
        selected_exercises = random.sample(exercises, min(4, len(exercises)))

        advice = f"Tailored for your age {age}, gender {gender}, and {category} category. Start slow, stay consistent, and consult a doctor before beginning."

        return {
            "level": level,
            "duration": duration,
            "exercises": selected_exercises,
            "advice": advice,
        }

    def get_motivational_quotes():
        return [
            "Your health is your wealth.",
            "Small steps lead to big changes.",
            "Consistency is key.",
            "Every healthy choice counts.",
        ]

    def get_bmi_recommendations(user):
        """
        Personalized AI recommendations based on user data.
        Returns (weekly_food_plan, daily_workout_plan, water_target_liters, calorie_target).
        """
        category = get_user_value(user, 'category', 'Normal')
        age = get_user_value(user, 'age', 30)
        gender = get_user_value(user, 'gender', 'Other')
        height = get_user_value(user, 'height', 170)
        weight = get_user_value(user, 'weight', 70)

        # Calculate personalized calories using BMR
        bmr = calculate_bmr(age, gender, height, weight)
        tdee = bmr * 1.2  # Sedentary

        if category == "Underweight":
            calories = int(tdee + 300)
            food = f"High-calorie nutritious foods: nuts, avocados, whole milk, lean meats, and whole grains. 5–6 small meals per day. Personalized for {gender} aged {age}."
            workout = f"Light strength training 3–4 days/week, focus on muscle gain, minimal cardio. Suitable for your age {age}."
            water = 2.0
        elif category == "Normal":
            calories = int(tdee)
            food = f"Balanced diet: vegetables, fruits, lean protein, whole grains. Limit processed sugar and fried foods. Tailored for {gender}."
            workout = f"30–45 minutes moderate exercise 5 days/week (mix of cardio and strength). Good for age {age}."
            water = 2.5
        elif category == "Overweight":
            calories = int(tdee - 500)
            food = f"Calorie-controlled, high-fiber meals. Focus on vegetables, lean protein, reduce refined carbs. Personalized plan for {gender} aged {age}."
            workout = f"45 minutes brisk walking/cardio 5 days/week + 2 days light strength. Appropriate for your profile."
            water = 3.0
        elif category == "Obese":
            calories = int(tdee - 750)
            food = f"Low-calorie, nutrient-dense meals. Avoid sugary snacks. Smaller, frequent meals. Customized for {gender}."
            workout = f"Start with 20–30 minutes low-impact cardio 5 days/week. Safe for age {age}."
            water = 3.0
        else:  # Severely Obese
            calories = int(tdee - 1000)
            food = f"Strict calorie deficit under medical guidance. Mostly vegetables, lean proteins. Avoid fried foods. Personalized advice."
            workout = f"Very low-impact activity 5–6 days/week. Consult doctor first, suitable for age {age}."
            water = 3.5

        # Vary plans slightly based on user hash
        import random
        random.seed(hash((age, gender, height, weight)))
        food_variations = ["Include more seasonal fruits.", "Try Mediterranean-style meals.", "Focus on local produce."]
        workout_variations = ["Add 5 min warm-up.", "Include flexibility exercises.", "Track progress weekly."]

        food += " " + random.choice(food_variations)
        workout += " " + random.choice(workout_variations)

        weekly_food_plan = f"Weekly Food Plan for {category} ({gender}, age {age}):\n- {food}\n- Spread meals evenly throughout the day.\n- Avoid excessive sugar and deep-fried foods.\n- Include seasonal fruits and vegetables."
        daily_workout_plan = f"Daily Workout Plan for {category} ({gender}, age {age}):\n- {workout}\n- Do a 5–10 minute warm-up and cool-down.\n- Include stretching to prevent injury."

        return weekly_food_plan, daily_workout_plan, water, calories

    def get_today_quote():
        """Get a fixed motivational quote."""
        return {
            "id": None,
            "quote_text": "Your health is your wealth.",
            "author": "Unknown",
        }

    def get_user_daily_tracking(user_id: int, on_date: date | None = None):
        """Fetch or create daily tracking record for a user."""
        if on_date is None:
            on_date = date.today()
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT * FROM daily_tracking
                WHERE user_id = ? AND track_date = ?
                """,
                (user_id, on_date),
            )
            record = cursor.fetchone()
            if not record:
                # Create a blank record
                cursor.execute(
                    """
                    INSERT INTO daily_tracking
                        (user_id, track_date, water_completed, food_completed,
                         workout_completed, challenge_completed, progress_percent)
                    VALUES (?, ?, 0, 0, 0, 0, 0)
                    """,
                    (user_id, on_date),
                )
                conn.commit()
                cursor.execute(
                    """
                    SELECT * FROM daily_tracking
                    WHERE user_id = ? AND track_date = ?
                    """,
                    (user_id, on_date),
                )
                record = cursor.fetchone()
            if record is not None:
                return dict(record)
            return record
        finally:
            cursor.close()
            conn.close()

    def update_daily_tracking(user_id: int, water: bool, food: bool, workout: bool, challenge: bool):
        """Update daily tracking flags and progress percentage."""
        on_date = date.today()
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Ensure record exists
            record = get_user_daily_tracking(user_id, on_date)

            # Only allow challenge to be completed if all three main tasks are done
            if challenge and not (water and food and workout):
                challenge = False

            total_items = 4
            completed = sum(
                [1 if water else 0, 1 if food else 0, 1 if workout else 0, 1 if challenge else 0]
            )
            progress = int((completed / total_items) * 100)

            cursor.execute(
                """
                UPDATE daily_tracking
                SET water_completed = ?,
                    food_completed = ?,
                    workout_completed = ?,
                    challenge_completed = ?,
                    progress_percent = ?
                WHERE id = ?
                """,
                (
                    int(water),
                    int(food),
                    int(workout),
                    int(challenge),
                    progress,
                    record["id"],
                ),
            )
            conn.commit()
            return progress
        finally:
            cursor.close()
            conn.close()

    # -----------------------------
    # Decorators
    # -----------------------------

    def login_required(role="user"):
        """Simple login_required decorator for user/admin."""

        def decorator(view_func):
            def wrapper(*args, **kwargs):
                if role == "admin":
                    if not session.get("admin_id"):
                        return redirect(url_for("admin_login"))
                else:
                    if not session.get("user_id"):
                        return redirect(url_for("user_login"))
                return view_func(*args, **kwargs)

            # Preserve function name for Flask
            wrapper.__name__ = view_func.__name__
            return wrapper

        return decorator

    # -----------------------------
    # Routes: Public
    # -----------------------------

    @app.route("/")
    def index():
        """Login selection page."""
        return render_template("login_selection.html")

    @app.route("/bmi", methods=["GET", "POST"])
    def bmi_calculator():
        """BMI Calculator page for the multi-step coaching flow."""
        quote = get_today_quote()
        quotes = get_motivational_quotes()
        bmi_result = None
        bmi_category = None
        saved = False

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            age = request.form.get("age")
            gender = request.form.get("gender")
            height = request.form.get("height")
            weight = request.form.get("weight")

            try:
                age = int(age)
                height = float(height)
                weight = float(weight)
            except (TypeError, ValueError):
                flash("Please provide valid numeric values for age, height, and weight.", "danger")
                return redirect(url_for("bmi_calculator"))

            if not name or age <= 0 or height <= 0 or weight <= 0:
                flash("Please complete all required fields with valid values.", "danger")
                return redirect(url_for("bmi_calculator"))

            bmi_result, bmi_category = calculate_bmi(height, weight)

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO health_flow
                        (name, age, gender, height, weight, bmi, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        age,
                        gender,
                        height,
                        weight,
                        bmi_result,
                        bmi_category,
                    ),
                )
                conn.commit()
                flow_user_id = cursor.lastrowid
                session["health_flow_user_id"] = flow_user_id
                saved = True
            except Exception as e:
                flash(f"Error saving data: {str(e)}. Please try again.", "danger")
                return redirect(url_for("bmi_calculator"))
            finally:
                cursor.close()
                conn.close()
        
        if saved:
            return redirect(url_for("diet"))

        return render_template(
            "bmi.html",
            quote=quote,
            quotes=quotes,
            bmi_result=bmi_result,
            bmi_category=bmi_category,
            saved=saved,
            current_step=1,
            total_steps=3,
            show_previous=False,
            show_next=True,
        )

    @app.route("/diet")
    def diet():
        """Diet page - Step 2 of multi-step coaching flow."""
        flow_user_id = session.get("health_flow_user_id")
        if not flow_user_id:
            return redirect(url_for("bmi_calculator"))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM health_flow WHERE id = ?", (flow_user_id,))
            user = cursor.fetchone()
            if not user:
                return redirect(url_for("bmi_calculator"))
            user = dict(user)
            diet = generate_diet_plan(user)
            quotes = get_motivational_quotes()
            quote = get_today_quote()
            return render_template(
                "diet.html",
                user=user,
                diet=diet,
                quotes=quotes,
                quote=quote,
                current_step=2,
                total_steps=3,
                show_previous=True,
                show_next=True,
            )
        finally:
            cursor.close()
            conn.close()

    @app.route("/workout")
    def workout():
        """Workout page - Step 3 of multi-step coaching flow."""
        flow_user_id = session.get("health_flow_user_id")
        if not flow_user_id:
            return redirect(url_for("bmi_calculator"))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM health_flow WHERE id = ?", (flow_user_id,))
            user = cursor.fetchone()
            if not user:
                return redirect(url_for("bmi_calculator"))
            user = dict(user)
            plan = generate_workout_plan(user)
            quotes = get_motivational_quotes()
            quote = get_today_quote()
            return render_template(
                "workout.html",
                user=user,
                plan=plan,
                quotes=quotes,
                quote=quote,
                current_step=3,
                total_steps=3,
                show_previous=True,
                show_next=False,
                show_complete=True,
            )
        finally:
            cursor.close()
            conn.close()

    @app.route("/flow_complete")
    def flow_complete():
        """Flow completion page - End of multi-step coaching."""
        flow_user_id = session.get("health_flow_user_id")
        if not flow_user_id:
            return redirect(url_for("bmi_calculator"))

        quote = get_today_quote()
        quotes = get_motivational_quotes()
        return render_template(
            "flow_complete.html",
            quote=quote,
            quotes=quotes,
        )

    @app.route("/challenge")
    def challenge():
        flow_user_id = session.get("health_flow_user_id")
        if not flow_user_id:
            return redirect(url_for("bmi_calculator"))

        user_id = session.get("user_id")
        tracking = None
        admin_messages = []
        if user_id:
            tracking = get_user_daily_tracking(user_id)
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    SELECT * FROM admin_messages
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 5
                    """,
                    (user_id,),
                )
                admin_messages_raw = cursor.fetchall()
                # Convert created_at strings to datetime objects for template
                admin_messages = []
                for msg in admin_messages_raw:
                    msg_dict = dict(msg)
                    if isinstance(msg_dict['created_at'], str):
                        msg_dict['created_at'] = datetime.fromisoformat(msg_dict['created_at'])
                    admin_messages.append(msg_dict)
            finally:
                cursor.close()
                conn.close()

        quotes = get_motivational_quotes()
        quote = get_today_quote()
        return render_template(
            "challenge.html",
            tracking=tracking,
            admin_messages=admin_messages,
            quotes=quotes,
            quote=quote,
        )

    # -----------------------------
    # Authentication Routes
    # -----------------------------

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT * FROM admin WHERE email = ?", (email,))
                admin = cursor.fetchone()
                if admin and check_password_hash(admin["password_hash"], password):
                    session.clear()
                    session["admin_id"] = admin["id"]
                    session["admin_email"] = admin["email"]

                    # Log login activity (reuse login_logs table)
                    cursor.execute(
                        """
                        INSERT INTO login_logs (user_id, is_admin, login_time)
                        VALUES (?, ?, ?)
                        """,
                        (None, 1, datetime.utcnow()),
                    )
                    conn.commit()
                    return redirect(url_for("admin_dashboard"))
                else:
                    flash("Invalid admin credentials.", "danger")
            finally:
                cursor.close()
                conn.close()

        return render_template("admin_login.html")

    @app.route("/user/login", methods=["GET", "POST"])
    def user_login():
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
                user = cursor.fetchone()
                if user and check_password_hash(user["password_hash"], password):
                    session.clear()
                    session["user_id"] = user["id"]
                    session["user_name"] = user["full_name"]

                    # Check for unread admin messages
                    cursor.execute(
                        """
                        SELECT * FROM admin_messages
                        WHERE user_id = ? AND is_read = 0
                        ORDER BY created_at DESC
                        """,
                        (user["id"],),
                    )
                    unread_messages = cursor.fetchall()

                    # log login activity
                    cursor.execute(
                        """
                        INSERT INTO login_logs (user_id, is_admin, login_time)
                        VALUES (?, ?, ?)
                        """,
                        (user["id"], 0, datetime.utcnow()),
                    )
                    conn.commit()

                    # If there are unread messages, redirect to dashboard with popup
                    if unread_messages:
                        session["show_admin_popup"] = True
                        session["unread_messages"] = [dict(msg) for msg in unread_messages]
                        return redirect(url_for("user_dashboard"))
                    else:
                        return redirect(url_for("bmi_calculator"))
                else:
                    flash("Invalid email or password.", "danger")
            finally:
                cursor.close()
                conn.close()

        return render_template("user_login.html")

    @app.route("/user/register", methods=["GET", "POST"])
    def user_register():
        if request.method == "POST":
            full_name = request.form.get("full_name")
            email = request.form.get("email")
            password = request.form.get("password")

            password_hash = generate_password_hash(password)

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                # Check if user already exists
                cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
                if cursor.fetchone():
                    flash("Email already registered. Please login instead.", "warning")
                    return redirect(url_for("user_login"))

                cursor.execute(
                    """
                    INSERT INTO users (full_name, email, password_hash, target_status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (full_name, email, password_hash, "Ongoing"),
                )
                conn.commit()
                flash("Registration successful. Please login.", "success")
                return redirect(url_for("user_login"))
            finally:
                cursor.close()
                conn.close()

        return render_template("user_register.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("index"))

    # -----------------------------
    # Admin Dashboard
    # -----------------------------

    @app.route("/admin/dashboard")
    @login_required(role="admin")
    def admin_dashboard():
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Total users
            cursor.execute("SELECT COUNT(*) AS total_users FROM users")
            total_users = cursor.fetchone()["total_users"]

            # Recent login logs
            cursor.execute(
                """
                SELECT ll.*, u.full_name, u.email
                FROM login_logs ll
                LEFT JOIN users u ON ll.user_id = u.id
                ORDER BY ll.login_time DESC
                LIMIT 20
                """
            )
            login_logs = cursor.fetchall()

            # User BMI and target status
            cursor.execute(
                """
                SELECT u.id, u.full_name, u.email, u.target_status,
                       br.height_cm, br.weight_kg, br.bmi_value, br.category,
                       br.created_at
                FROM users u
                LEFT JOIN bmi_records br
                    ON br.id = (
                        SELECT id FROM bmi_records
                        WHERE user_id = u.id
                        ORDER BY created_at DESC
                        LIMIT 1
                    )
                ORDER BY u.full_name ASC
                """
            )
            user_bmi_records = cursor.fetchall()

            # Daily challenge completion summary (today)
            today = date.today()
            cursor.execute(
                """
                SELECT u.full_name, dt.*
                FROM daily_tracking dt
                JOIN users u ON dt.user_id = u.id
                WHERE dt.track_date = ?
                ORDER BY u.full_name ASC
                """,
                (today,),
            )
            daily_tracking = cursor.fetchall()

            return render_template(
                "admin_dashboard.html",
                total_users=total_users,
                login_logs=login_logs,
                user_bmi_records=user_bmi_records,
                daily_tracking=daily_tracking,
            )
        finally:
            cursor.close()
            conn.close()

    @app.route("/admin/message", methods=["POST"])
    @login_required(role="admin")
    def admin_send_message():
        user_id = request.form.get("user_id")
        message = request.form.get("message")
        if not user_id or not message:
            flash("User and message are required.", "warning")
            return redirect(url_for("admin_dashboard"))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO admin_messages (admin_id, user_id, message, created_at, is_read)
                VALUES (?, ?, ?, ?, 0)
                """,
                (session.get("admin_id"), user_id, message, datetime.utcnow()),
            )
            conn.commit()
            flash("Message sent to user.", "success")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/delete_user", methods=["POST"])
    @login_required(role="admin")
    def admin_delete_user():
        """Delete a user and related records (simple cascade).

        This performs basic cleanup of related tables to avoid foreign key errors.
        """
        user_id = request.form.get("user_id")
        if not user_id:
            flash("User selection required.", "warning")
            return redirect(url_for("admin_dashboard"))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Attempt to remove related records first to avoid FK constraints
            cursor.execute("DELETE FROM bmi_records WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM daily_tracking WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM admin_messages WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM login_logs WHERE user_id = ?", (user_id,))
            # Finally remove the user
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            flash("User deleted successfully.", "success")
        except Exception:
            conn.rollback()
            flash("Failed to delete user. Check database constraints.", "danger")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/update_target", methods=["POST"])
    @login_required(role="admin")
    def admin_update_target():
        user_id = request.form.get("user_id")
        target_status = request.form.get("target_status")

        if not user_id or not target_status:
            flash("User and target status are required.", "warning")
            return redirect(url_for("admin_dashboard"))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET target_status = ? WHERE id = ?",
                (target_status, user_id),
            )
            conn.commit()
            flash("User target status updated.", "success")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("admin_dashboard"))

    # -----------------------------
    # User Dashboard & BMI Logic
    # -----------------------------

    @app.route("/user/dashboard", methods=["GET", "POST"])
    @login_required(role="user")
    def user_dashboard():
        user_id = session.get("user_id")
        bmi_result = None
        bmi_category = None
        weekly_food_plan = None
        daily_workout_plan = None
        water_target = None
        calorie_target = None
        improvement_status = None
        latest_bmi_record = None

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if request.method == "POST":
                try:
                    height_cm = float(request.form.get("height_cm"))
                    weight_kg = float(request.form.get("weight_kg"))
                except (TypeError, ValueError):
                    flash("Please enter valid height and weight.", "danger")
                    return redirect(url_for("user_dashboard"))

                bmi_result, bmi_category = calculate_bmi(height_cm, weight_kg)
                if bmi_result is None:
                    flash("Invalid height provided.", "danger")
                    return redirect(url_for("user_dashboard"))

                # Insert BMI record
                cursor.execute(
                    """
                    INSERT INTO bmi_records
                        (user_id, height_cm, weight_kg, bmi_value, category, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, height_cm, weight_kg, bmi_result, bmi_category, datetime.utcnow()),
                )
                conn.commit()

            # Fetch the latest BMI record
            cursor.execute(
                """
                SELECT * FROM bmi_records
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 2
                """,
                (user_id,),
            )
            bmi_records = cursor.fetchall()
            if bmi_records:
                latest_bmi_record = bmi_records[0]
                bmi_result = latest_bmi_record["bmi_value"]
                bmi_category = latest_bmi_record["category"]

                # Improvement analytics: compare latest with previous
                if len(bmi_records) == 2:
                    previous_bmi = bmi_records[1]["bmi_value"]
                    if bmi_result < previous_bmi:
                        improvement_status = "improved"
                    elif bmi_result > previous_bmi:
                        improvement_status = "worsened"
                    else:
                        improvement_status = "stable"

                # Get AI recommendations (initial with category)
                (
                    weekly_food_plan,
                    daily_workout_plan,
                    water_target,
                    calorie_target,
                ) = get_bmi_recommendations({"category": bmi_category})

            # Fetch user profile & target status
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            if user is not None:
                user = dict(user)

            # Update recommendations with full user data
            if user:
                (
                    weekly_food_plan,
                    daily_workout_plan,
                    water_target,
                    calorie_target,
                ) = get_bmi_recommendations(user)

            # Daily tracking info
            tracking = get_user_daily_tracking(user_id)

            # Reset challenge completed on each login/dashboard load
            tracking['challenge_completed'] = 0

            # Recalculate progress based on the three main tasks (challenge is reset)
            completed_count = sum([
                1 if tracking['water_completed'] else 0,
                1 if tracking['food_completed'] else 0,
                1 if tracking['workout_completed'] else 0
            ])
            tracking['progress_percent'] = int((completed_count / 4) * 100)

            # Admin messages
            cursor.execute(
                """
                SELECT * FROM admin_messages
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (user_id,),
            )
            admin_messages = [dict(msg) for msg in cursor.fetchall()]

            # Motivational quote
            quote = get_today_quote()

            # Motivational message based on target completion
            motivational_message = None
            if user and user.get("target_status") == "Completed":
                motivational_message = "Amazing job completing your target! Keep up the great work and maintain your healthy habits."
            else:
                motivational_message = "You are on your journey. Stay consistent today – even a small step counts."

            # Improvement analytics message
            improvement_message = None
            if improvement_status == "improved":
                improvement_message = "Your BMI has improved compared to your last record. Fantastic progress!"
            elif improvement_status == "worsened":
                improvement_message = (
                    "Your BMI has increased compared to your last record. Consider tightening your food plan "
                    "and staying more consistent with workouts."
                )
            elif improvement_status == "stable":
                improvement_message = "Your BMI is stable. Keep following your plan to see gradual improvements."

            return render_template(
                "user_dashboard.html",
                user=user,
                bmi_result=bmi_result,
                bmi_category=bmi_category,
                weekly_food_plan=weekly_food_plan,
                daily_workout_plan=daily_workout_plan,
                water_target=water_target,
                calorie_target=calorie_target,
                tracking=tracking,
                admin_messages=admin_messages,
                quote=quote,
                motivational_message=motivational_message,
                improvement_message=improvement_message,
                show_admin_popup=session.pop("show_admin_popup", False),
                unread_messages=session.pop("unread_messages", []),
            )
        finally:
            cursor.close()
            conn.close()

    @app.route("/mark_messages_read", methods=["POST"])
    @login_required(role="user")
    def mark_messages_read():
        """Mark admin messages as read for the current user."""
        user_id = session.get("user_id")
        if not user_id:
            return {"success": False}, 400

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE admin_messages SET is_read = 1 WHERE user_id = ? AND is_read = 0",
                (user_id,),
            )
            conn.commit()
            return {"success": True}
        finally:
            cursor.close()
            conn.close()

    # -----------------------------
    # Daily Tracking (AJAX) {
    # -----------------------------

    @app.route("/user/daily-tracking", methods=["POST"])
    @login_required(role="user")
    def update_tracking_route():
        user_id = session.get("user_id")
        data = request.get_json() or {}

        water = bool(data.get("water_completed"))
        food = bool(data.get("food_completed"))
        workout = bool(data.get("workout_completed"))
        challenge = bool(data.get("challenge_completed"))

        progress = update_daily_tracking(user_id, water, food, workout, challenge)

        # Simple encouragement message based on progress
        if progress == 100:
            message = "Congratulations! You have completed all your health goals for today."
        elif progress >= 50:
            message = "Great job. You're more than halfway there – keep going!"
        else:
            message = "Good start! Make a small healthy choice right now to move closer to your goal."

        return jsonify({"success": True, "progress": progress, "message": message})

    # -----------------------------
    # Simple health reminders (static, simulated)
    # -----------------------------

    @app.context_processor
    def inject_reminders():
        """Inject reminder text into all templates."""
        reminders = [
            "Drink a glass of water now.",
            "Take a 5-minute walk or stretch break.",
            "Review your meal plan for today.",
        ]
        return {"global_reminders": reminders}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

