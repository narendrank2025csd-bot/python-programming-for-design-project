from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import re
import hmac
import json
import secrets
import uuid
from contextlib import contextmanager
from datetime import datetime, date, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import ml_lab

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "startup_tycoon.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-development-secret-before-deploying")

MISSIONS = [
    {"id": 1, "title": "Save Unsold Food", "category": "Sustainability", "difficulty": "Easy",
     "problem": "Restaurants and bakeries throw away edible food at closing time.",
     "task": "Design a service that connects shops with nearby customers who can buy surplus food at a discount.",
     "hint": "Think about food safety, pickup windows, restaurant onboarding, and how your startup earns money.",
     "xp": 100, "coins": 250, "unlock": 1},
    {"id": 2, "title": "Digitize Small Shops", "category": "Small Business", "difficulty": "Easy",
     "problem": "Small retailers often track stock, sales, and customer credit manually.",
     "task": "Propose a simple, low-cost mobile tool that helps shopkeepers manage daily operations.",
     "hint": "Consider offline use, local languages, easy onboarding, and a monthly pricing plan.",
     "xp": 150, "coins": 350, "unlock": 1},
    {"id": 3, "title": "Smarter Farming", "category": "Agriculture", "difficulty": "Medium",
     "problem": "Farmers may struggle to find trusted, localized crop information and market prices.",
     "task": "Create an affordable farming assistant that helps farmers make better-informed decisions.",
     "hint": "Think about reliable data, regional languages, farmer trust, and partnerships with experts.",
     "xp": 250, "coins": 600, "unlock": 2},
    {"id": 4, "title": "Affordable Last-Mile Delivery", "category": "Logistics", "difficulty": "Medium",
     "problem": "Local businesses can find small, nearby deliveries expensive and hard to coordinate.",
     "task": "Design a shared delivery network for small merchants in one neighborhood.",
     "hint": "Consider route density, delivery fees, rider safety, and service reliability.",
     "xp": 300, "coins": 750, "unlock": 2},
    {"id": 5, "title": "Win Your First Investor", "category": "Fundraising", "difficulty": "Hard",
     "problem": "Your prototype has early interest, but you need funding to test whether the business can scale.",
     "task": "Write a concise investor pitch covering customer problem, solution, market, revenue, competitors, and use of funds.",
     "hint": "Be specific about who pays, what evidence you have, and what milestone the money will unlock.",
     "xp": 500, "coins": 1500, "unlock": 3},
    {"id": 6, "title": "Reduce E-Waste", "category": "Circular Economy", "difficulty": "Hard",
     "problem": "People and small offices often store unused electronics because safe repair or recycling is inconvenient.",
     "task": "Create a trusted collection, refurbishment, or recycling service with a sustainable business model.",
     "hint": "Consider data wiping, certified partners, transparent pricing, and responsible disposal.",
     "xp": 450, "coins": 1200, "unlock": 3},
]

SHOP_ITEMS = [
    {"id": "suit", "name": "Founder Suit", "kind": "Outfit", "price": 300, "emoji": "🕴️", "description": "Dress for your next investor pitch."},
    {"id": "watch", "name": "Smart Watch", "kind": "Accessory", "price": 250, "emoji": "⌚", "description": "A little founder flair."},
    {"id": "laptop", "name": "Business Laptop", "kind": "Equipment", "price": 500, "emoji": "💻", "description": "Unlocks advanced market-analysis missions."},
    {"id": "research", "name": "Research Kit", "kind": "Equipment", "price": 700, "emoji": "🔬", "description": "Unlocks extra hints on difficult missions."},
    {"id": "car", "name": "Sports Car", "kind": "Vehicle", "price": 2000, "emoji": "🏎️", "description": "A premium founder ride."},
    {"id": "office", "name": "Startup Office", "kind": "Property", "price": 1500, "emoji": "🏢", "description": "Your own headquarters."},
    {"id": "headphones", "name": "Focus Headphones", "kind": "Accessory", "price": 400, "emoji": "🎧", "description": "Block out the noise and build."},
    {"id": "drone", "name": "Survey Drone", "kind": "Equipment", "price": 900, "emoji": "🚁", "description": "A useful tool for field research missions."},
]

MISSION_REWARDS = {
    "Easy": {"xp": 20, "coins": 10},
    "Medium": {"xp": 50, "coins": 25},
    "Hard": {"xp": 100, "coins": 50},
    "Epic": {"xp": 200, "coins": 100},
}

SKILL_BRANCHES = {
    "TECHNOLOGY": [
        ("beginner-coder", "Beginner Coder", 0, "Technology"),
        ("problem-solver", "Problem Solver", 100, "Technology"),
        ("software-builder", "Software Builder", 300, "Technology"),
        ("engineering-master", "Engineering Master", 700, "Technology"),
    ],
    "CREATIVITY": [
        ("idea-explorer", "Idea Explorer", 0, "Creativity"),
        ("visual-creator", "Visual Creator", 100, "Creativity"),
        ("creative-designer", "Creative Designer", 300, "Creativity"),
        ("creative-director", "Creative Director", 700, "Creativity"),
    ],
    "KNOWLEDGE": [
        ("curious-learner", "Curious Learner", 0, "Knowledge"),
        ("researcher", "Researcher", 100, "Knowledge"),
        ("strategist", "Strategist", 300, "Knowledge"),
        ("knowledge-master", "Knowledge Master", 700, "Knowledge"),
    ],
    "DISCIPLINE": [
        ("getting-started", "Getting Started", 0, "Discipline"),
        ("consistent-worker", "Consistent Worker", 100, "Discipline"),
        ("focus-master", "Focus Master", 300, "Discipline"),
        ("productivity-legend", "Productivity Legend", 700, "Discipline"),
    ],
    "ENTREPRENEURSHIP": [
        ("idea-founder", "Idea Founder", 0, "Entrepreneurship"),
        ("first-project", "First Project", 100, "Entrepreneurship"),
        ("business-builder", "Business Builder", 300, "Entrepreneurship"),
        ("startup-leader", "Startup Leader", 700, "Entrepreneurship"),
    ],
}
SKILL_CATEGORY_MATCHES = {
    "TECHNOLOGY": ("tech", "software", "engineering", "coding", "program"),
    "CREATIVITY": ("creativ", "design", "art"),
    "KNOWLEDGE": ("knowledge", "research", "learning", "education"),
    "DISCIPLINE": ("discipline", "productivity", "focus", "habit"),
    "ENTREPRENEURSHIP": ("business", "entrepreneur", "startup", "fundraising", "sustainability", "agriculture", "logistics", "circular"),
}

ACHIEVEMENTS = [
    ("first-step", "First Step", "Complete your first mission.", "tasks", 1),
    ("daily-builder", "Daily Builder", "Complete five missions.", "tasks", 5),
    ("week-of-work", "Week of Work", "Reach a seven-day streak.", "streak", 7),
    ("level-five", "Founder Level 5", "Reach character level 5.", "level", 5),
    ("office-owner", "Office Owner", "Purchase your first office upgrade.", "upgrade", 1),
    ("team-builder", "Team Builder", "Hire your first employee.", "employee", 1),
    ("boss-slayer", "Boss Slayer", "Complete a boss battle.", "boss", 1),
    ("early-startup", "Early Startup", "Reach startup level 3.", "startup", 3),
    ("growing-company", "Growing Company", "Reach startup level 5.", "startup", 5),
    ("industry-leader", "Industry Leader", "Reach startup level 8.", "startup", 8),
]

OFFICE_UPGRADES = [
    {"id": "better-desk", "name": "Better Desk", "description": "A dedicated founder workspace.", "price": 150, "level": 1, "requires": None, "emoji": "🪑"},
    {"id": "improved-computer", "name": "Improved Computer", "description": "A faster setup for ambitious projects.", "price": 300, "level": 1, "requires": "better-desk", "emoji": "💻"},
    {"id": "office-decoration", "name": "Office Decoration", "description": "Make the workspace feel like yours.", "price": 250, "level": 1, "requires": "better-desk", "emoji": "🪴"},
    {"id": "additional-workspace", "name": "Additional Workspace", "description": "Make room for your first teammate.", "price": 600, "level": 2, "requires": "improved-computer", "emoji": "🛋️"},
    {"id": "meeting-room", "name": "Meeting Room", "description": "A place to plan the next big move.", "price": 900, "level": 3, "requires": "additional-workspace", "emoji": "🗣️"},
    {"id": "development-department", "name": "Development Department", "description": "Unlock a focused engineering department.", "price": 1200, "level": 3, "requires": "improved-computer", "emoji": "🧑‍💻"},
    {"id": "research-department", "name": "Research Department", "description": "Build a home for customer insight.", "price": 1500, "level": 5, "requires": "meeting-room", "emoji": "🔬"},
    {"id": "larger-headquarters", "name": "Larger Headquarters", "description": "Expand into an industry-leading HQ.", "price": 3000, "level": 8, "requires": "research-department", "emoji": "🏢"},
]

EMPLOYEE_ROLES = [
    {"role": "Developer", "price": 500, "level": 2, "upgrade": "additional-workspace", "emoji": "👩‍💻"},
    {"role": "Designer", "price": 450, "level": 2, "upgrade": "additional-workspace", "emoji": "🎨"},
    {"role": "Marketing Specialist", "price": 650, "level": 3, "upgrade": "meeting-room", "emoji": "📣"},
    {"role": "Researcher", "price": 750, "level": 4, "upgrade": "research-department", "emoji": "🔎"},
    {"role": "Project Manager", "price": 900, "level": 5, "upgrade": "meeting-room", "emoji": "📋"},
]

VILLAGE_BUILDINGS = [
    {"id": "headquarters", "name": "Founder HQ", "kind": "hq", "emoji": "🏰", "unlock": 1, "x": 50, "y": 47,
     "purpose": "Command center for your startup empire.", "quests": []},
    {"id": "quest-board", "name": "Quest Board", "kind": "board", "emoji": "📜", "unlock": 1, "x": 25, "y": 45,
     "purpose": "Accept productive quests and track your journey.", "quests": ["customer-interviews", "founder-focus"]},
    {"id": "workshop", "name": "Maker Workshop", "kind": "workshop", "emoji": "🛠️", "unlock": 1, "x": 72, "y": 44,
     "purpose": "Turn a rough idea into a useful first version.", "quests": ["prototype-sketch", "build-first-version"]},
    {"id": "resource-storage", "name": "Resource Vault", "kind": "storage", "emoji": "🧰", "unlock": 1, "x": 32, "y": 70,
     "purpose": "Keep track of the real resources your founder journey already uses.", "quests": []},
    {"id": "marketplace", "name": "Market Square", "kind": "market", "emoji": "🏪", "unlock": 2, "x": 77, "y": 69,
     "purpose": "Meet customers, shape your offer, and understand the market.", "quests": ["customer-interviews", "pricing-test"]},
    {"id": "training-center", "name": "Focus Lodge", "kind": "training", "emoji": "🧘", "unlock": 2, "x": 54, "y": 78,
     "purpose": "Build consistent habits and develop practical skills.", "quests": ["learning-sprint", "founder-focus"]},
    {"id": "research-lab", "name": "Research Grove", "kind": "research", "emoji": "🔬", "unlock": 3, "x": 80, "y": 28,
     "purpose": "Explore opportunities and learn from evidence.", "quests": ["market-map", "learning-sprint"]},
    {"id": "mission-hall", "name": "Mission Hall", "kind": "mission", "emoji": "🏆", "unlock": 3, "x": 47, "y": 23,
     "purpose": "Review your existing startup challenges and milestones.", "quests": []},
]

VILLAGE_QUESTS = [
    {"id": "customer-interviews", "title": "Listen to the Locals", "category": "Entrepreneurship",
     "building": "marketplace", "difficulty": "Easy", "description": "Talk with potential customers about a problem they face.",
     "objective": "Have at least one real customer conversation. Record the problem they described, what surprised you, and one follow-up question.",
     "requirements": ["Describe a real conversation and the customer's problem.", "Share one insight and a next step."],
     "xp": 20, "coins": 10},
    {"id": "founder-focus", "title": "A Focused Founder Hour", "category": "Discipline",
     "building": "training-center", "difficulty": "Easy", "description": "Complete one uninterrupted focus session on a meaningful goal.",
     "objective": "Set a clear 25-minute goal, complete the focus session, and write what you moved forward and what comes next.",
     "requirements": ["Name your focus goal and work completed.", "Reflect on the session and next action."],
     "xp": 20, "coins": 10},
    {"id": "prototype-sketch", "title": "Sketch the First Draft", "category": "Creativity",
     "building": "workshop", "difficulty": "Medium", "description": "Create a simple sketch or outline for your first product idea.",
     "objective": "Make a tangible first draft. Describe what you made, who it helps, and one improvement you will try.",
     "requirements": ["Describe a real draft or sketch and its intended user.", "Name an improvement based on your work."],
     "xp": 50, "coins": 25},
    {"id": "build-first-version", "title": "Build One Small Piece", "category": "Technology",
     "building": "workshop", "difficulty": "Hard", "description": "Make a small working piece of a project instead of planning the whole thing.",
     "objective": "Complete one concrete piece of a project and record what works, what does not, and the next test.",
     "requirements": ["Explain the specific project piece you built or changed.", "Describe a result and the next test."],
     "xp": 100, "coins": 50},
    {"id": "market-map", "title": "Map the Opportunity", "category": "Knowledge",
     "building": "research-lab", "difficulty": "Medium", "description": "Research an opportunity and compare at least two existing alternatives.",
     "objective": "Use available sources to compare the customer problem, alternatives, and one evidence-backed opportunity.",
     "requirements": ["Name sources or alternatives you researched.", "Summarize an insight and a question to validate."],
     "xp": 50, "coins": 25},
    {"id": "learning-sprint", "title": "Learn, Then Apply", "category": "Knowledge",
     "building": "research-lab", "difficulty": "Easy", "description": "Learn one practical concept and use it on a current project.",
     "objective": "Complete a short learning session, record the key idea, and explain how you applied or will apply it.",
     "requirements": ["State what you learned and how you learned it.", "Describe how it applies to your project."],
     "xp": 20, "coins": 10},
    {"id": "pricing-test", "title": "Test the Offer", "category": "Entrepreneurship",
     "building": "marketplace", "difficulty": "Hard", "description": "Write a simple offer and test whether a potential customer understands it.",
     "objective": "Share or discuss one clear offer with a potential customer. Record their response and your change to the offer.",
     "requirements": ["Describe the offer and a real customer's response.", "Explain what you learned and changed."],
     "xp": 100, "coins": 50},
]

BOSS_BATTLES = [
    {"id": "first-customer", "name": "The First Customer", "description": "Prove your idea can solve a real customer's problem.", "level": 2, "xp": 150, "coins": 75,
     "steps": ["Describe one specific customer and their problem.", "Explain your simplest solution and how you will test it with that customer."]},
    {"id": "market-rival", "name": "The Market Rival", "description": "Show why your startup deserves a place in a crowded market.", "level": 4, "xp": 300, "coins": 150,
     "steps": ["Name a competitor or alternative and explain its customer appeal.", "Describe your advantage and one measurable experiment to validate it."]},
]

@contextmanager
def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with connect_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            coins INTEGER NOT NULL DEFAULT 1000,
            xp INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            mission_id INTEGER NOT NULL,
            answer TEXT NOT NULL,
            score INTEGER NOT NULL,
            feedback TEXT NOT NULL,
            xp_awarded INTEGER NOT NULL,
            coins_awarded INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, mission_id)
        );
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            item_id TEXT NOT NULL,
            purchased_at TEXT NOT NULL,
            UNIQUE(user_id, item_id)
        );
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            amount INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS game_profiles (
            user_id INTEGER PRIMARY KEY REFERENCES users(id),
            startup_name TEXT NOT NULL DEFAULT 'My Startup',
            startup_xp INTEGER NOT NULL DEFAULT 0,
            startup_level INTEGER NOT NULL DEFAULT 1,
            current_streak INTEGER NOT NULL DEFAULT 0,
            longest_streak INTEGER NOT NULL DEFAULT 0,
            last_completion_date TEXT
        );
        CREATE TABLE IF NOT EXISTS user_missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            deadline TEXT,
            is_daily INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            UNIQUE(id, user_id)
        );
        CREATE TABLE IF NOT EXISTS mission_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            mission_id INTEGER NOT NULL REFERENCES user_missions(id),
            cycle_key TEXT NOT NULL,
            xp_awarded INTEGER NOT NULL,
            coins_awarded INTEGER NOT NULL,
            completed_at TEXT NOT NULL,
            UNIQUE(user_id, mission_id, cycle_key)
        );
        CREATE TABLE IF NOT EXISTS deleted_game_missions (
            user_id INTEGER NOT NULL REFERENCES users(id),
            mission_id INTEGER NOT NULL REFERENCES user_missions(id),
            deleted_at TEXT NOT NULL,
            PRIMARY KEY(user_id, mission_id)
        );
        CREATE TABLE IF NOT EXISTS unlocked_skills (
            user_id INTEGER NOT NULL REFERENCES users(id),
            skill_id TEXT NOT NULL,
            unlocked_at TEXT NOT NULL,
            PRIMARY KEY(user_id, skill_id)
        );
        CREATE TABLE IF NOT EXISTS unlocked_achievements (
            user_id INTEGER NOT NULL REFERENCES users(id),
            achievement_id TEXT NOT NULL,
            unlocked_at TEXT NOT NULL,
            PRIMARY KEY(user_id, achievement_id)
        );
        CREATE TABLE IF NOT EXISTS office_upgrades (
            user_id INTEGER NOT NULL REFERENCES users(id),
            upgrade_id TEXT NOT NULL,
            purchased_at TEXT NOT NULL,
            PRIMARY KEY(user_id, upgrade_id)
        );
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            role TEXT NOT NULL,
            name TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,
            hired_at TEXT NOT NULL,
            UNIQUE(user_id, role)
        );
        CREATE TABLE IF NOT EXISTS boss_progress (
            user_id INTEGER NOT NULL REFERENCES users(id),
            boss_id TEXT NOT NULL,
            current_step INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            PRIMARY KEY(user_id, boss_id)
        );
        CREATE TABLE IF NOT EXISTS boss_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            boss_id TEXT NOT NULL,
            step_number INTEGER NOT NULL,
            answer TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            UNIQUE(user_id, boss_id, step_number)
        );
        CREATE TABLE IF NOT EXISTS player_village_quests (
            user_id INTEGER NOT NULL REFERENCES users(id),
            quest_id TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('active','completed')),
            accepted_at TEXT NOT NULL,
            submitted_at TEXT,
            action_notes TEXT,
            outcome_notes TEXT,
            next_step_notes TEXT,
            xp_reward INTEGER NOT NULL,
            coin_reward INTEGER NOT NULL,
            PRIMARY KEY(user_id, quest_id)
        );
        CREATE TABLE IF NOT EXISTS village_buildings (
            user_id INTEGER NOT NULL REFERENCES users(id),
            building_id TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1 CHECK(level BETWEEN 1 AND 5),
            updated_at TEXT NOT NULL,
            PRIMARY KEY(user_id, building_id)
        );
        CREATE TABLE IF NOT EXISTS ml_experiments (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            dataset_name TEXT NOT NULL,
            dataset_version TEXT NOT NULL,
            dataset_origin TEXT NOT NULL,
            task TEXT NOT NULL CHECK(task IN ('regression','classification','clustering')),
            target_column TEXT,
            feature_columns TEXT NOT NULL,
            algorithm TEXT NOT NULL,
            metrics_json TEXT NOT NULL DEFAULT '{}',
            config_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL CHECK(status IN ('failed','trained','saved')),
            artifact_id TEXT UNIQUE,
            model_version INTEGER NOT NULL DEFAULT 1,
            deployment_status TEXT NOT NULL DEFAULT 'not_deployed'
                CHECK(deployment_status IN ('not_deployed','deployed')),
            error_message TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ml_experiments_user_created
            ON ml_experiments(user_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS ml_quest_claims (
            user_id INTEGER NOT NULL REFERENCES users(id),
            quest_id TEXT NOT NULL,
            claimed_at TEXT NOT NULL,
            PRIMARY KEY(user_id, quest_id)
        );
        CREATE TABLE IF NOT EXISTS ml_dataset_explorations (
            user_id INTEGER NOT NULL REFERENCES users(id),
            dataset_name TEXT NOT NULL,
            explored_at TEXT NOT NULL,
            PRIMARY KEY(user_id, dataset_name)
        );
        CREATE TABLE IF NOT EXISTS ml_predictions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            experiment_id TEXT NOT NULL REFERENCES ml_experiments(id),
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ml_model_comparisons (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            left_experiment_id TEXT NOT NULL REFERENCES ml_experiments(id),
            right_experiment_id TEXT NOT NULL REFERENCES ml_experiments(id),
            metrics_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, left_experiment_id, right_experiment_id)
        );
        """)
        ml_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(ml_experiments)")
        }
        if "model_version" not in ml_columns:
            db.execute(
                "ALTER TABLE ml_experiments ADD COLUMN model_version INTEGER NOT NULL DEFAULT 1"
            )
        if "deployment_status" not in ml_columns:
            db.execute(
                "ALTER TABLE ml_experiments ADD COLUMN deployment_status TEXT NOT NULL DEFAULT 'not_deployed'"
            )
        db.execute(
            "INSERT OR IGNORE INTO game_profiles(user_id) SELECT id FROM users"
        )
        db.execute("""
            UPDATE game_profiles
            SET startup_xp=COALESCE((
                SELECT SUM(xp_awarded) FROM submissions WHERE submissions.user_id=game_profiles.user_id
            ), 0),
            startup_level=1 + COALESCE((
                SELECT SUM(xp_awarded) FROM submissions WHERE submissions.user_id=game_profiles.user_id
            ), 0) / 300
            WHERE startup_xp=0
        """)
init_db()

def xp_to_next_level(level):
    return 300

def utc_now():
    return datetime.now(timezone.utc)

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    with connect_db() as db:
        return db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

def level_for(xp):
    return 1 + xp // 300

def game_today():
    return utc_now().date().isoformat()

def skill_catalog():
    return [
        {"branch": branch, "id": skill_id, "name": name, "xp": threshold,
         "category": category, "previous": nodes[index - 1][0] if index else None}
        for branch, nodes in SKILL_BRANCHES.items()
        for index, (skill_id, name, threshold, category) in enumerate(nodes)
    ]

def skill_category_counts(db, user_id):
    counts = {branch: 0 for branch in SKILL_BRANCHES}
    completed_categories = db.execute(
        "SELECT m.category, COUNT(*) AS total FROM mission_completions c "
        "JOIN user_missions m ON m.id=c.mission_id WHERE c.user_id=? GROUP BY m.category",
        (user_id,)
    ).fetchall()
    legacy_categories = db.execute("SELECT mission_id FROM submissions WHERE user_id=?", (user_id,)).fetchall()
    legacy_category_map = {mission["id"]: mission["category"].lower() for mission in MISSIONS}
    for row in completed_categories:
        category_name = row["category"].lower()
        for branch, needles in SKILL_CATEGORY_MATCHES.items():
            if any(needle in category_name for needle in needles):
                counts[branch] += row["total"]
    for row in legacy_categories:
        category_name = legacy_category_map.get(row["mission_id"], "")
        for branch, needles in SKILL_CATEGORY_MATCHES.items():
            if any(needle in category_name for needle in needles):
                counts[branch] += 1
    village_completions = db.execute(
        "SELECT quest_id FROM player_village_quests WHERE user_id=? AND state='completed'",
        (user_id,)
    ).fetchall()
    quest_categories = {quest["id"]: quest["category"].lower() for quest in VILLAGE_QUESTS}
    for row in village_completions:
        category_name = quest_categories.get(row["quest_id"], "")
        for branch, needles in SKILL_CATEGORY_MATCHES.items():
            if any(needle in category_name for needle in needles):
                counts[branch] += 1
    ml_quest_count = db.execute(
        "SELECT COUNT(*) FROM ml_quest_claims WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    counts["KNOWLEDGE"] += ml_quest_count
    return counts

def sync_game_progress(db, user_id):
    user = db.execute("SELECT xp FROM users WHERE id=?", (user_id,)).fetchone()
    profile = db.execute("SELECT * FROM game_profiles WHERE user_id=?", (user_id,)).fetchone()
    completed_count = db.execute(
        "SELECT (SELECT COUNT(*) FROM mission_completions WHERE user_id=?) + "
        "(SELECT COUNT(*) FROM submissions WHERE user_id=?) + "
        "(SELECT COUNT(*) FROM player_village_quests WHERE user_id=? AND state='completed') + "
        "(SELECT COUNT(*) FROM ml_quest_claims WHERE user_id=?)",
        (user_id, user_id, user_id, user_id)
    ).fetchone()[0]
    level = level_for(user["xp"])
    category_counts = skill_category_counts(db, user_id)
    for skill in skill_catalog():
        branch_index = next(index for index, node in enumerate(SKILL_BRANCHES[skill["branch"]]) if node[0] == skill["id"])
        if user["xp"] >= skill["xp"] and category_counts[skill["branch"]] >= branch_index and (
            not skill["previous"] or db.execute(
                "SELECT 1 FROM unlocked_skills WHERE user_id=? AND skill_id=?",
                (user_id, skill["previous"])
            ).fetchone()
        ):
            db.execute(
                "INSERT OR IGNORE INTO unlocked_skills(user_id,skill_id,unlocked_at) VALUES(?,?,?)",
                (user_id, skill["id"], utc_now().isoformat())
            )
    achievement_values = {
        "tasks": completed_count, "streak": profile["longest_streak"],
        "level": level,
        "upgrade": db.execute("SELECT COUNT(*) FROM office_upgrades WHERE user_id=?", (user_id,)).fetchone()[0],
        "employee": db.execute("SELECT COUNT(*) FROM employees WHERE user_id=?", (user_id,)).fetchone()[0],
        "boss": db.execute("SELECT COUNT(*) FROM boss_progress WHERE user_id=? AND completed_at IS NOT NULL", (user_id,)).fetchone()[0],
        "startup": profile["startup_level"],
    }
    for achievement_id, _, _, condition, threshold in ACHIEVEMENTS:
        if achievement_values[condition] >= threshold:
            db.execute(
                "INSERT OR IGNORE INTO unlocked_achievements(user_id,achievement_id,unlocked_at) VALUES(?,?,?)",
                (user_id, achievement_id, utc_now().isoformat())
            )

def update_streak(db, user_id, completed_at):
    today = date.fromisoformat(completed_at[:10])
    profile = db.execute("SELECT * FROM game_profiles WHERE user_id=?", (user_id,)).fetchone()
    last = profile["last_completion_date"]
    if last == today.isoformat():
        return
    current = profile["current_streak"] + 1 if last == (today - timedelta(days=1)).isoformat() else 1
    db.execute(
        "UPDATE game_profiles SET current_streak=?, longest_streak=MAX(longest_streak,?), last_completion_date=? WHERE user_id=?",
        (current, current, today.isoformat(), user_id)
    )

def score_answer(answer):
    """Offline rubric-based evaluator. It rewards relevant ideas, not sheer answer length."""
    cleaned = re.sub(r"\s+", " ", answer.strip())
    low = cleaned.lower()
    if len(cleaned) < 35:
        return 10, [
            "Your idea needs more detail before it can be evaluated fairly.",
            "Explain the target customer, the solution, and how it could work in practice."
        ]
    criteria = {
        "Problem understanding": (["problem", "because", "struggle", "waste", "need", "pain point"], 20),
        "Customer clarity": (["customer", "shopkeeper", "farmer", "restaurant", "student", "business", "user", "merchant"], 20),
        "Practical solution": (["app", "platform", "service", "deliver", "connect", "tool", "marketplace", "software", "collect"], 20),
        "Revenue model": (["subscription", "commission", "fee", "revenue", "charge", "sell", "premium", "profit", "pricing"], 20),
        "Validation and risks": (["test", "pilot", "survey", "feedback", "safety", "partner", "cost", "competitor", "measure", "risk"], 20),
    }
    score = 0
    missing = []
    for label, (keywords, points) in criteria.items():
        if any(word in low for word in keywords):
            score += points
        else:
            missing.append(label)
    feedback = []
    if score >= 80:
        feedback.append("Strong business outline! You covered several important parts of a viable startup.")
    elif score >= 60:
        feedback.append("Good foundation. Make the business model and first test more concrete.")
    elif score >= 40:
        feedback.append("You have a starting point. Add more detail about customers and how the solution operates.")
    else:
        feedback.append("Keep going: turn the idea into a clear, testable business proposal.")
    suggestions = {
        "Problem understanding": "Describe the exact problem and who experiences it.",
        "Customer clarity": "Name one specific target customer group and how you will reach them.",
        "Practical solution": "Explain the first version of the product and the customer journey.",
        "Revenue model": "State who pays, how much they might pay, and why.",
        "Validation and risks": "Suggest a small pilot, customer interviews, and one risk to test."
    }
    if missing:
        feedback.append("Next improvements:")
        feedback.extend("• " + suggestions[m] for m in missing[:3])
    feedback.append("This is an offline keyword-based score, not an AI or expert assessment. Use real customer research before making business decisions.")
    return score, feedback

def login_required():
    if not current_user():
        flash("Please log in or create an account to continue.", "warning")
        return False
    return True

@app.context_processor
def inject_globals():
    user = current_user()
    return {"player": user, "player_level": level_for(user["xp"]) if user else 1,
            "missions": MISSIONS, "shop_items": SHOP_ITEMS, "mission_rewards": MISSION_REWARDS}

@app.route("/")
def index():
    user = current_user()
    if user:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
            flash("Username must be 3–20 characters using letters, numbers, or underscores.", "danger")
            return render_template("auth.html", mode="register")
        if len(password) < 8:
            flash("Use a password with at least 8 characters.", "danger")
            return render_template("auth.html", mode="register")
        try:
            with connect_db() as db:
                cur = db.execute("INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)",
                    (username, generate_password_hash(password), utc_now().isoformat()))
                uid = cur.lastrowid
                db.execute("INSERT INTO game_profiles(user_id) VALUES(?)", (uid,))
                db.execute("INSERT INTO wallet_transactions(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
                    (uid, 1000, "Welcome bonus", utc_now().isoformat()))
            session["user_id"] = uid
            flash("Welcome to the founder's journey! You received 1,000 coins.", "success")
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("That username is already taken. Try another one.", "danger")
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with connect_db() as db:
            user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "danger")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if not login_required(): return redirect(url_for("login"))
    user = current_user()
    with connect_db() as db:
        completed_rows = db.execute("SELECT mission_id,score FROM submissions WHERE user_id=?", (user["id"],)).fetchall()
        owned = db.execute("SELECT item_id FROM inventory WHERE user_id=?", (user["id"],)).fetchall()
        recent = db.execute("SELECT * FROM submissions WHERE user_id=? ORDER BY id DESC LIMIT 3", (user["id"],)).fetchall()
    completed = {r["mission_id"]: r["score"] for r in completed_rows}
    owned_ids = {r["item_id"] for r in owned}
    available = [m for m in MISSIONS if m["unlock"] <= level_for(user["xp"]) and m["id"] not in completed]
    next_milestone = level_for(user["xp"]) * 300
    progress = int((user["xp"] % 300) / 300 * 100)
    return render_template("dashboard.html", user=user, completed=completed, owned_ids=owned_ids,
        available=available, recent=recent, progress=progress, next_milestone=next_milestone,
        completed_count=len(completed))

@app.route("/game")
def game_dashboard():
    if not login_required(): return redirect(url_for("login"))
    user = current_user()
    today = game_today()
    category = request.args.get("category", "").strip()
    difficulty = request.args.get("difficulty", "").strip()
    status = request.args.get("status", "active").strip()
    if difficulty and difficulty not in MISSION_REWARDS:
        difficulty = ""
    if status not in {"active", "completed", "all"}:
        status = "active"
    with connect_db() as db:
        db.execute("INSERT OR IGNORE INTO game_profiles(user_id) VALUES(?)", (user["id"],))
        db.execute(
            "UPDATE game_profiles SET current_streak=0 WHERE user_id=? "
            "AND last_completion_date IS NOT NULL AND last_completion_date<?",
            (user["id"], (date.fromisoformat(today) - timedelta(days=1)).isoformat())
        )
        missions = db.execute(
            "SELECT m.*, c.completed_at AS last_completed, c.cycle_key AS completed_cycle "
            "FROM user_missions m LEFT JOIN mission_completions c ON c.user_id=m.user_id AND c.mission_id=m.id "
            "AND c.cycle_key=CASE WHEN m.is_daily=1 THEN ? ELSE 'once' END "
            "WHERE m.user_id=? AND NOT EXISTS (SELECT 1 FROM deleted_game_missions d WHERE d.user_id=m.user_id AND d.mission_id=m.id) "
            "ORDER BY m.deadline IS NULL, m.deadline, m.id DESC",
            (today, user["id"])
        ).fetchall()
        upgrades = db.execute("SELECT upgrade_id FROM office_upgrades WHERE user_id=?", (user["id"],)).fetchall()
        employees = db.execute("SELECT * FROM employees WHERE user_id=? ORDER BY id", (user["id"],)).fetchall()
        skills = db.execute("SELECT skill_id FROM unlocked_skills WHERE user_id=?", (user["id"],)).fetchall()
        achievement_rows = db.execute("SELECT achievement_id,unlocked_at FROM unlocked_achievements WHERE user_id=?", (user["id"],)).fetchall()
        profile = db.execute("SELECT * FROM game_profiles WHERE user_id=?", (user["id"],)).fetchone()
        total_completed = db.execute(
            "SELECT (SELECT COUNT(*) FROM submissions WHERE user_id=?) + "
            "(SELECT COUNT(*) FROM mission_completions WHERE user_id=?) + "
            "(SELECT COUNT(*) FROM player_village_quests WHERE user_id=? AND state='completed') + "
            "(SELECT COUNT(*) FROM ml_quest_claims WHERE user_id=?)",
            (user["id"], user["id"], user["id"], user["id"])
        ).fetchone()[0]
        history = db.execute(
            "SELECT c.*, m.title, m.category, m.difficulty FROM mission_completions c "
            "JOIN user_missions m ON m.id=c.mission_id WHERE c.user_id=? ORDER BY c.id DESC LIMIT 8",
            (user["id"],)
        ).fetchall()
        legacy_history = db.execute(
            "SELECT s.xp_awarded,s.coins_awarded,s.created_at AS completed_at,s.mission_id "
            "FROM submissions s WHERE s.user_id=? ORDER BY s.id DESC LIMIT 8",
            (user["id"],)
        ).fetchall()
        boss_rows = db.execute("SELECT * FROM boss_progress WHERE user_id=?", (user["id"],)).fetchall()
        boss_answers = db.execute(
            "SELECT boss_id,step_number,answer FROM boss_answers WHERE user_id=? ORDER BY boss_id,step_number",
            (user["id"],)
        ).fetchall()
        wallet_history = db.execute("SELECT * FROM wallet_transactions WHERE user_id=? ORDER BY id DESC LIMIT 8", (user["id"],)).fetchall()
        sync_game_progress(db, user["id"])
        skill_rows = db.execute("SELECT skill_id FROM unlocked_skills WHERE user_id=?", (user["id"],)).fetchall()
        achievement_rows = db.execute("SELECT achievement_id,unlocked_at FROM unlocked_achievements WHERE user_id=?", (user["id"],)).fetchall()
        category_counts = skill_category_counts(db, user["id"])
    mission_lookup = {mission["id"]: mission for mission in MISSIONS}
    combined_history = [
        {"title": entry["title"], "category": entry["category"], "difficulty": entry["difficulty"],
         "xp_awarded": entry["xp_awarded"], "coins_awarded": entry["coins_awarded"],
         "completed_at": entry["completed_at"]}
        for entry in history
    ]
    for entry in legacy_history:
        legacy_mission = mission_lookup.get(entry["mission_id"])
        if legacy_mission:
            combined_history.append(
                {"title": legacy_mission["title"], "category": legacy_mission["category"],
                 "difficulty": legacy_mission["difficulty"], "xp_awarded": entry["xp_awarded"],
                 "coins_awarded": entry["coins_awarded"], "completed_at": entry["completed_at"]}
            )
    combined_history.sort(key=lambda entry: entry["completed_at"], reverse=True)
    combined_history = combined_history[:8]
    owned_upgrades = {row["upgrade_id"] for row in upgrades}
    owned_skills = {row["skill_id"] for row in skill_rows}
    unlocked_achievements = {row["achievement_id"]: row["unlocked_at"] for row in achievement_rows}
    current_level = level_for(user["xp"])
    next_level_xp = xp_to_next_level(current_level)
    level_progress = int((user["xp"] % 300) / 300 * 100)
    startup_stage = (
        "INDUSTRY LEADER" if profile["startup_level"] >= 8 else
        "GROWING COMPANY" if profile["startup_level"] >= 5 else
        "EARLY STARTUP" if profile["startup_level"] >= 3 else "FREELANCER"
    )
    filtered_missions = []
    categories = sorted({mission["category"] for mission in missions})
    for mission in missions:
        done = mission["last_completed"] is not None
        if category and mission["category"] != category: continue
        if difficulty and mission["difficulty"] != difficulty: continue
        if status == "active" and done: continue
        if status == "completed" and not done: continue
        filtered_missions.append(mission)
    battle_progress = {row["boss_id"]: row for row in boss_rows}
    return render_template(
        "game.html", user=user, profile=profile, missions=filtered_missions, categories=categories,
        category_filter=category, difficulty_filter=difficulty, status_filter=status,
        current_level=current_level, next_level_xp=next_level_xp, level_progress=level_progress,
        completed_count=total_completed, startup_stage=startup_stage, owned_upgrades=owned_upgrades,
        employees=employees, office_level=1 + len(owned_upgrades),
        skill_catalog=skill_catalog(), owned_skills=owned_skills,
        achievements=ACHIEVEMENTS, unlocked_achievements=unlocked_achievements,
        mission_rewards=MISSION_REWARDS, office_upgrades=OFFICE_UPGRADES,
        employee_roles=EMPLOYEE_ROLES, boss_battles=BOSS_BATTLES,
        battle_progress=battle_progress, boss_answers=boss_answers, history=combined_history, wallet_history=wallet_history,
        category_counts=category_counts,
        today=today, game_date=date.fromisoformat(today).strftime("%A, %B %d")
    )

@app.route("/game/history")
def game_history():
    if not login_required(): return redirect(url_for("login"))
    user = current_user()
    with connect_db() as db:
        game_rows = db.execute(
            "SELECT c.xp_awarded,c.coins_awarded,c.completed_at,m.title,m.category,m.difficulty "
            "FROM mission_completions c JOIN user_missions m ON m.id=c.mission_id "
            "WHERE c.user_id=? ORDER BY c.completed_at DESC",
            (user["id"],)
        ).fetchall()
        legacy_rows = db.execute(
            "SELECT s.xp_awarded,s.coins_awarded,s.created_at AS completed_at,s.mission_id,s.score "
            "FROM submissions s WHERE s.user_id=? ORDER BY s.created_at DESC",
            (user["id"],)
        ).fetchall()
        boss_rows = db.execute(
            "SELECT a.boss_id,a.step_number,a.answer,a.submitted_at,p.completed_at "
            "FROM boss_answers a LEFT JOIN boss_progress p ON p.user_id=a.user_id AND p.boss_id=a.boss_id "
            "WHERE a.user_id=? ORDER BY a.submitted_at DESC",
            (user["id"],)
        ).fetchall()
        village_quest_rows = db.execute(
            "SELECT quest_id,submitted_at,xp_reward,coin_reward FROM player_village_quests "
            "WHERE user_id=? AND state='completed'",
            (user["id"],)
        ).fetchall()
    mission_lookup = {mission["id"]: mission for mission in MISSIONS}
    history = [
        {"title": row["title"], "category": row["category"], "difficulty": row["difficulty"],
         "xp_awarded": row["xp_awarded"], "coins_awarded": row["coins_awarded"],
         "completed_at": row["completed_at"], "detail": "Daily mission reward"}
        for row in game_rows
    ]
    for row in legacy_rows:
        mission = mission_lookup.get(row["mission_id"])
        if mission:
            history.append(
                {"title": mission["title"], "category": mission["category"],
                 "difficulty": mission["difficulty"], "xp_awarded": row["xp_awarded"],
                 "coins_awarded": row["coins_awarded"], "completed_at": row["completed_at"],
                 "detail": f"Startup challenge · score {row['score']}/100"}
            )
    for row in boss_rows:
        battle = next((entry for entry in BOSS_BATTLES if entry["id"] == row["boss_id"]), None)
        if battle:
            history.append(
                {"title": f"{battle['name']} · Step {row['step_number'] + 1}",
                 "category": "Boss battle", "difficulty": "Epic", "xp_awarded": battle["xp"] if row["completed_at"] and row["step_number"] == len(battle["steps"]) - 1 else 0,
                 "coins_awarded": battle["coins"] if row["completed_at"] and row["step_number"] == len(battle["steps"]) - 1 else 0,
                 "completed_at": row["submitted_at"], "detail": row["answer"]}
            )
    quest_lookup = {quest["id"]: quest for quest in VILLAGE_QUESTS}
    for row in village_quest_rows:
        quest = quest_lookup.get(row["quest_id"])
        if quest:
            history.append(
                {"title": quest["title"], "category": quest["category"],
                 "difficulty": quest["difficulty"], "xp_awarded": row["xp_reward"],
                 "coins_awarded": row["coin_reward"], "completed_at": row["submitted_at"],
                 "detail": "Quest Village field notes submitted"}
            )
    history.sort(key=lambda entry: entry["completed_at"], reverse=True)
    return render_template("history.html", history=history)

@app.route("/village")
def village():
    if not login_required(): return redirect(url_for("login"))
    user = current_user()
    level = level_for(user["xp"])
    with connect_db() as db:
        db.execute(
            "INSERT OR IGNORE INTO game_profiles(user_id) VALUES(?)", (user["id"],)
        )
        for building in VILLAGE_BUILDINGS:
            if level >= building["unlock"]:
                db.execute(
                    "INSERT OR IGNORE INTO village_buildings(user_id,building_id,level,updated_at) VALUES(?,?,1,?)",
                    (user["id"], building["id"], utc_now().isoformat())
                )
        profile = db.execute(
            "SELECT * FROM game_profiles WHERE user_id=?", (user["id"],)
        ).fetchone()
        buildings = db.execute(
            "SELECT building_id,level FROM village_buildings WHERE user_id=?",
            (user["id"],)
        ).fetchall()
        quest_rows = db.execute(
            "SELECT * FROM player_village_quests WHERE user_id=? ORDER BY accepted_at DESC",
            (user["id"],)
        ).fetchall()
        completed_tasks = db.execute(
            "SELECT (SELECT COUNT(*) FROM submissions WHERE user_id=?) + "
            "(SELECT COUNT(*) FROM mission_completions WHERE user_id=?) + "
            "(SELECT COUNT(*) FROM player_village_quests WHERE user_id=? AND state='completed') + "
            "(SELECT COUNT(*) FROM ml_quest_claims WHERE user_id=?)",
            (user["id"], user["id"], user["id"], user["id"])
        ).fetchone()[0]
        legacy_rows = db.execute(
            "SELECT mission_id FROM submissions WHERE user_id=?", (user["id"],)
        ).fetchall()
        inventory_count = db.execute(
            "SELECT COUNT(*) FROM inventory WHERE user_id=?", (user["id"],)
        ).fetchone()[0]
        personal_missions = db.execute(
            "SELECT m.*, CASE WHEN m.is_daily=1 THEN "
            "EXISTS(SELECT 1 FROM mission_completions c WHERE c.user_id=m.user_id AND c.mission_id=m.id AND c.cycle_key=?) "
            "ELSE EXISTS(SELECT 1 FROM mission_completions c WHERE c.user_id=m.user_id AND c.mission_id=m.id AND c.cycle_key='once') "
            "END AS completed_today FROM user_missions m WHERE m.user_id=? "
            "AND NOT EXISTS(SELECT 1 FROM deleted_game_missions d WHERE d.user_id=m.user_id AND d.mission_id=m.id) "
            "ORDER BY m.id DESC LIMIT 6",
            (game_today(), user["id"])
        ).fetchall()
    building_levels = {row["building_id"]: row["level"] for row in buildings}
    quest_states = {row["quest_id"]: dict(row) for row in quest_rows}
    quest_catalog = []
    for definition in VILLAGE_QUESTS:
        quest = dict(definition)
        quest["state"] = quest_states.get(quest["id"], {}).get("state", "available")
        quest["quest_level"] = next(
            building["unlock"] for building in VILLAGE_BUILDINGS
            if building["id"] == quest["building"]
        )
        quest_catalog.append(quest)
    unlocked_features = [
        building["name"] for building in VILLAGE_BUILDINGS
        if building["unlock"] <= level
    ]
    board = []
    for definition in VILLAGE_BUILDINGS:
        building = dict(definition)
        building["level"] = building_levels.get(building["id"], 0)
        building["is_unlocked"] = level >= building["unlock"]
        building["quest_count"] = sum(
            1 for quest in quest_catalog
            if quest["building"] == building["id"] and quest["state"] == "available"
            and level >= quest["quest_level"]
        )
        board.append(building)
    total_xp_to_next_level = 300
    active_quest_count = sum(1 for row in quest_rows if row["state"] == "active")
    reputation = completed_tasks * 10 + profile["startup_level"] * 25
    return render_template(
        "village.html", user=user, profile=profile, level=level,
        xp_progress=int((user["xp"] % 300) / total_xp_to_next_level * 100),
        xp_remaining=total_xp_to_next_level - (user["xp"] % 300),
        reputation=reputation, completed_tasks=completed_tasks,
        inventory_count=inventory_count,
        buildings=board, building_levels=building_levels,
        quest_catalog=quest_catalog, quest_states=quest_states,
        quest_rewards=MISSION_REWARDS, active_quest_count=active_quest_count,
        personal_missions=personal_missions, legacy_missions=MISSIONS,
        legacy_completed={row["mission_id"] for row in legacy_rows},
        unlocked_features=unlocked_features,
        focused_building=request.args.get("building", ""),
        focused_quest=request.args.get("quest", ""),
    )

@app.route("/village/quests/<quest_id>/accept", methods=["POST"])
def accept_village_quest(quest_id):
    if not login_required(): return redirect(url_for("login"))
    quest = next((entry for entry in VILLAGE_QUESTS if entry["id"] == quest_id), None)
    if not quest:
        flash("That village quest is not available.", "danger")
        return redirect(url_for("village"))
    user = current_user()
    required_building = next(
        building for building in VILLAGE_BUILDINGS if building["id"] == quest["building"]
    )
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        current_level = level_for(
            db.execute("SELECT xp FROM users WHERE id=?", (user["id"],)).fetchone()["xp"]
        )
        if current_level < required_building["unlock"]:
            flash(f"{required_building['name']} unlocks at Founder Level {required_building['unlock']}.", "warning")
            return redirect(url_for("village", building=quest["building"]))
        if db.execute(
            "SELECT 1 FROM player_village_quests WHERE user_id=? AND quest_id=?",
            (user["id"], quest_id)
        ).fetchone():
            flash("This quest has already been accepted and cannot be accepted again.", "warning")
            return redirect(url_for("village", building=quest["building"], quest=quest_id))
        rewards = MISSION_REWARDS[quest["difficulty"]]
        try:
            db.execute(
                "INSERT INTO player_village_quests(user_id,quest_id,state,accepted_at,xp_reward,coin_reward) "
                "VALUES(?,?,'active',?,?,?)",
                (user["id"], quest_id, utc_now().isoformat(), rewards["xp"], rewards["coins"])
            )
        except sqlite3.IntegrityError:
            flash("This quest has already been accepted.", "warning")
            return redirect(url_for("village", building=quest["building"], quest=quest_id))
    flash(f"Quest accepted: {quest['title']}. Your progress is saved.", "success")
    return redirect(url_for("village", building=quest["building"], quest=quest_id))

@app.route("/village/quests/<quest_id>/submit", methods=["POST"])
def submit_village_quest(quest_id):
    if not login_required(): return redirect(url_for("login"))
    quest = next((entry for entry in VILLAGE_QUESTS if entry["id"] == quest_id), None)
    if not quest:
        flash("That village quest is not available.", "danger")
        return redirect(url_for("village"))
    action_notes = request.form.get("action_notes", "").strip()
    outcome_notes = request.form.get("outcome_notes", "").strip()
    next_step_notes = request.form.get("next_step_notes", "").strip()
    if not 40 <= len(action_notes) <= 2000:
        flash("Describe the action you completed in 40–2,000 characters.", "warning")
        return redirect(url_for("village", building=quest["building"], quest=quest_id))
    if not 30 <= len(outcome_notes) <= 2000:
        flash("Describe the result or evidence in 30–2,000 characters.", "warning")
        return redirect(url_for("village", building=quest["building"], quest=quest_id))
    if not 20 <= len(next_step_notes) <= 1000:
        flash("Add your next step in 20–1,000 characters.", "warning")
        return redirect(url_for("village", building=quest["building"], quest=quest_id))
    if len(set(action_notes.lower().split())) < 8 or len(set(outcome_notes.lower().split())) < 6:
        flash("Add specific details in your action and result notes before submitting.", "warning")
        return redirect(url_for("village", building=quest["building"], quest=quest_id))
    user = current_user()
    now = utc_now().isoformat()
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        old_level = level_for(
            db.execute("SELECT xp FROM users WHERE id=?", (user["id"],)).fetchone()["xp"]
        )
        assignment = db.execute(
            "SELECT * FROM player_village_quests WHERE user_id=? AND quest_id=?",
            (user["id"], quest_id)
        ).fetchone()
        if not assignment:
            flash("Accept this quest before submitting its completion.", "warning")
            return redirect(url_for("village", building=quest["building"], quest=quest_id))
        if assignment["state"] != "active":
            flash("This quest has already been completed and rewarded.", "warning")
            return redirect(url_for("village", building=quest["building"], quest=quest_id))
        update = db.execute(
            "UPDATE player_village_quests SET state='completed',submitted_at=?,action_notes=?,outcome_notes=?,next_step_notes=? "
            "WHERE user_id=? AND quest_id=? AND state='active'",
            (now, action_notes, outcome_notes, next_step_notes, user["id"], quest_id)
        )
        if update.rowcount != 1:
            flash("This quest has already been submitted.", "warning")
            return redirect(url_for("village", building=quest["building"], quest=quest_id))
        rewards_xp = assignment["xp_reward"]
        rewards_coins = assignment["coin_reward"]
        db.execute(
            "UPDATE users SET xp=xp+?,coins=coins+? WHERE id=?",
            (rewards_xp, rewards_coins, user["id"])
        )
        db.execute(
            "UPDATE game_profiles SET startup_xp=startup_xp+?,startup_level=1+(startup_xp+?)/300 "
            "WHERE user_id=?",
            (rewards_xp, rewards_xp, user["id"])
        )
        update_streak(db, user["id"], now)
        db.execute(
            "INSERT INTO wallet_transactions(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
            (user["id"], rewards_coins, f"Village quest: {quest['title']}", now)
        )
        sync_game_progress(db, user["id"])
        new_level = level_for(
            db.execute("SELECT xp FROM users WHERE id=?", (user["id"],)).fetchone()["xp"]
        )
    level_message = f" Founder Level {new_level} reached!" if new_level > old_level else ""
    new_plots = [
        building["name"] for building in VILLAGE_BUILDINGS
        if old_level < building["unlock"] <= new_level
    ]
    plot_message = f" New village buildings unlocked: {', '.join(new_plots)}." if new_plots else ""
    flash(f"Quest complete! +{rewards_xp} XP · +{rewards_coins} coins.{level_message}{plot_message}", "success")
    return redirect(url_for("village", building=quest["building"], quest=quest_id))

@app.route("/village/buildings/<building_id>/upgrade", methods=["POST"])
def upgrade_village_building(building_id):
    if not login_required(): return redirect(url_for("login"))
    building = next((entry for entry in VILLAGE_BUILDINGS if entry["id"] == building_id), None)
    if not building:
        flash("Building not found.", "danger")
        return redirect(url_for("village"))
    user = current_user()
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        current_level = level_for(
            db.execute("SELECT xp FROM users WHERE id=?", (user["id"],)).fetchone()["xp"]
        )
        if current_level < building["unlock"]:
            flash(f"{building['name']} unlocks at Founder Level {building['unlock']}.", "warning")
            return redirect(url_for("village", building=building_id))
        stored = db.execute(
            "SELECT level FROM village_buildings WHERE user_id=? AND building_id=?",
            (user["id"], building_id)
        ).fetchone()
        if not stored:
            db.execute(
                "INSERT INTO village_buildings(user_id,building_id,level,updated_at) VALUES(?,?,1,?)",
                (user["id"], building_id, utc_now().isoformat())
            )
            current_building_level = 1
        else:
            current_building_level = stored["level"]
        if current_building_level >= 5:
            flash("This building is already at its maximum level.", "info")
            return redirect(url_for("village", building=building_id))
        price = current_building_level * 250
        debit = db.execute(
            "UPDATE users SET coins=coins-? WHERE id=? AND coins>=?",
            (price, user["id"], price)
        )
        if debit.rowcount != 1:
            flash(f"This upgrade costs {price} coins. Complete more quests to earn coins.", "warning")
            return redirect(url_for("village", building=building_id))
        db.execute(
            "UPDATE village_buildings SET level=level+1,updated_at=? WHERE user_id=? AND building_id=? AND level=?",
            (utc_now().isoformat(), user["id"], building_id, current_building_level)
        )
        db.execute(
            "INSERT INTO wallet_transactions(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
            (user["id"], -price, f"Village building upgrade: {building['name']}", utc_now().isoformat())
        )
    flash(f"{building['name']} upgraded to Level {current_building_level + 1}.", "success")
    return redirect(url_for("village", building=building_id))

def validate_mission_form(form):
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    category = form.get("category", "").strip()
    difficulty = form.get("difficulty", "").strip()
    if not 3 <= len(title) <= 100:
        return None, "Mission titles must be 3–100 characters."
    if not 5 <= len(description) <= 1000:
        return None, "Mission descriptions must be 5–1,000 characters."
    if not 2 <= len(category) <= 40:
        return None, "Categories must be 2–40 characters."
    if difficulty not in MISSION_REWARDS:
        return None, "Choose a valid mission difficulty."
    try:
        duration = int(form.get("duration_minutes", ""))
        if not 1 <= duration <= 1440:
            raise ValueError
    except ValueError:
        return None, "Estimated duration must be between 1 and 1,440 minutes."
    deadline = form.get("deadline", "").strip() or None
    if deadline:
        try:
            datetime.strptime(deadline, "%Y-%m-%d")
        except ValueError:
            return None, "Choose a valid deadline."
        if deadline < game_today():
            return None, "Choose a deadline that is today or later."
    return {
        "title": title, "description": description, "category": category,
        "difficulty": difficulty, "duration": duration, "deadline": deadline,
        "is_daily": 1 if form.get("is_daily") == "on" else 0,
    }, None

@app.route("/game/missions/create", methods=["POST"])
def create_game_mission():
    if not login_required(): return redirect(url_for("login"))
    values, error = validate_mission_form(request.form)
    if error:
        flash(error, "danger")
        return redirect(url_for("game_dashboard"))
    user = current_user()
    with connect_db() as db:
        db.execute(
            "INSERT INTO user_missions(user_id,title,description,category,difficulty,duration_minutes,deadline,is_daily,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (user["id"], values["title"], values["description"], values["category"], values["difficulty"],
             values["duration"], values["deadline"], values["is_daily"], utc_now().isoformat())
        )
    flash("Mission added to your board.", "success")
    return redirect(url_for("game_dashboard"))

@app.route("/game/missions/<int:mission_id>/edit", methods=["POST"])
def edit_game_mission(mission_id):
    if not login_required(): return redirect(url_for("login"))
    values, error = validate_mission_form(request.form)
    if error:
        flash(error, "danger")
        return redirect(url_for("game_dashboard"))
    user = current_user()
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        mission = db.execute(
            "SELECT id,is_daily FROM user_missions WHERE id=? AND user_id=? AND NOT EXISTS "
            "(SELECT 1 FROM mission_completions WHERE mission_id=user_missions.id AND user_id=? "
            "AND cycle_key=CASE WHEN is_daily=1 THEN ? ELSE 'once' END) "
            "AND NOT EXISTS (SELECT 1 FROM deleted_game_missions WHERE mission_id=user_missions.id AND user_id=?)",
            (mission_id, user["id"], user["id"], game_today(), user["id"])
        ).fetchone()
        if not mission:
            flash("Mission not found, deleted, or already completed for this cycle.", "warning")
            return redirect(url_for("game_dashboard"))
        has_history = db.execute(
            "SELECT 1 FROM mission_completions WHERE mission_id=? AND user_id=? LIMIT 1",
            (mission_id, user["id"])
        ).fetchone()
        if has_history and mission["is_daily"] != values["is_daily"]:
            flash("A mission's recurrence cannot change after it has a reward history.", "warning")
            return redirect(url_for("game_dashboard"))
        db.execute(
            "UPDATE user_missions SET title=?,description=?,category=?,difficulty=?,duration_minutes=?,deadline=?,is_daily=? "
            "WHERE id=? AND user_id=?",
            (values["title"], values["description"], values["category"], values["difficulty"],
             values["duration"], values["deadline"], values["is_daily"], mission_id, user["id"])
        )
    flash("Mission updated.", "success")
    return redirect(url_for("game_dashboard"))

@app.route("/game/missions/<int:mission_id>/delete", methods=["POST"])
def delete_game_mission(mission_id):
    if not login_required(): return redirect(url_for("login"))
    user = current_user()
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        mission = db.execute(
            "SELECT id FROM user_missions WHERE id=? AND user_id=? AND NOT EXISTS "
            "(SELECT 1 FROM deleted_game_missions WHERE mission_id=user_missions.id AND user_id=?)",
            (mission_id, user["id"], user["id"])
        ).fetchone()
        if not mission:
            flash("Mission not found or it does not belong to your account.", "warning")
            return redirect(url_for("game_dashboard"))
        db.execute(
            "INSERT INTO deleted_game_missions(user_id,mission_id,deleted_at) VALUES(?,?,?)",
            (user["id"], mission_id, utc_now().isoformat())
        )
    flash("Mission deleted.", "info")
    return redirect(url_for("game_dashboard"))

@app.route("/game/missions/<int:mission_id>/complete", methods=["POST"])
def complete_game_mission(mission_id):
    if not login_required(): return redirect(url_for("login"))
    user = current_user()
    completed_at = utc_now().isoformat()
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        mission = db.execute(
            "SELECT * FROM user_missions WHERE id=? AND user_id=? AND NOT EXISTS "
            "(SELECT 1 FROM deleted_game_missions WHERE mission_id=user_missions.id AND user_id=?)",
            (mission_id, user["id"], user["id"])
        ).fetchone()
        if not mission:
            flash("Mission not found.", "danger")
            return redirect(url_for("game_dashboard"))
        if mission["deadline"] and mission["deadline"] < game_today():
            flash("This mission's deadline has passed.", "warning")
            return redirect(url_for("game_dashboard"))
        cycle_key = game_today() if mission["is_daily"] else "once"
        rewards = MISSION_REWARDS[mission["difficulty"]]
        try:
            db.execute(
                "INSERT INTO mission_completions(user_id,mission_id,cycle_key,xp_awarded,coins_awarded,completed_at) VALUES(?,?,?,?,?,?)",
                (user["id"], mission_id, cycle_key, rewards["xp"], rewards["coins"], completed_at)
            )
        except sqlite3.IntegrityError:
            flash("This mission has already earned rewards for this completion cycle.", "warning")
            return redirect(url_for("game_dashboard"))
        old_level = level_for(db.execute("SELECT xp FROM users WHERE id=?", (user["id"],)).fetchone()["xp"])
        db.execute("UPDATE users SET xp=xp+?, coins=coins+? WHERE id=?",
                   (rewards["xp"], rewards["coins"], user["id"]))
        new_level = level_for(db.execute("SELECT xp FROM users WHERE id=?", (user["id"],)).fetchone()["xp"])
        db.execute(
            "UPDATE game_profiles SET startup_xp=startup_xp+?, startup_level=1+(startup_xp+?)/300 WHERE user_id=?",
            (rewards["xp"], rewards["xp"], user["id"])
        )
        update_streak(db, user["id"], completed_at)
        db.execute(
            "INSERT INTO wallet_transactions(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
            (user["id"], rewards["coins"], f"Daily mission: {mission['title']}", completed_at)
        )
        sync_game_progress(db, user["id"])
    level_message = f" Level up! Founder Level {new_level}." if new_level > old_level else ""
    flash(f"Mission complete: +{rewards['xp']} XP and {rewards['coins']} coins!{level_message}", "success")
    return redirect(url_for("game_dashboard"))

@app.route("/game/startup", methods=["POST"])
def rename_startup():
    if not login_required(): return redirect(url_for("login"))
    name = request.form.get("startup_name", "").strip()
    if not 2 <= len(name) <= 50:
        flash("Startup names must be 2–50 characters.", "danger")
        return redirect(url_for("game_dashboard"))
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE game_profiles SET startup_name=? WHERE user_id=?", (name, current_user()["id"]))
    flash("Startup name updated.", "success")
    return redirect(url_for("game_dashboard"))

@app.route("/game/upgrades/<upgrade_id>/buy", methods=["POST"])
def buy_office_upgrade(upgrade_id):
    if not login_required(): return redirect(url_for("login"))
    item = next((entry for entry in OFFICE_UPGRADES if entry["id"] == upgrade_id), None)
    if not item:
        flash("Office upgrade not found.", "danger")
        return redirect(url_for("game_dashboard"))
    user = current_user()
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM office_upgrades WHERE user_id=? AND upgrade_id=?", (user["id"], upgrade_id)).fetchone():
            flash("You already own this upgrade.", "warning")
            return redirect(url_for("game_dashboard"))
        level = level_for(db.execute("SELECT xp FROM users WHERE id=?", (user["id"],)).fetchone()["xp"])
        if level < item["level"]:
            flash(f"This upgrade unlocks at character level {item['level']}.", "warning")
            return redirect(url_for("game_dashboard"))
        if item["requires"] and not db.execute(
            "SELECT 1 FROM office_upgrades WHERE user_id=? AND upgrade_id=?", (user["id"], item["requires"])
        ).fetchone():
            flash("Purchase the prerequisite office upgrade first.", "warning")
            return redirect(url_for("game_dashboard"))
        debit = db.execute("UPDATE users SET coins=coins-? WHERE id=? AND coins>=?", (item["price"], user["id"], item["price"]))
        if debit.rowcount != 1:
            flash("Not enough coins for this upgrade.", "danger")
            return redirect(url_for("game_dashboard"))
        db.execute("INSERT INTO office_upgrades(user_id,upgrade_id,purchased_at) VALUES(?,?,?)",
                   (user["id"], upgrade_id, utc_now().isoformat()))
        db.execute("INSERT INTO wallet_transactions(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
                   (user["id"], -item["price"], f"Office upgrade: {item['name']}", utc_now().isoformat()))
        sync_game_progress(db, user["id"])
    flash(f"{item['name']} added to your office.", "success")
    return redirect(url_for("game_dashboard"))

@app.route("/game/employees/hire", methods=["POST"])
def hire_employee():
    if not login_required(): return redirect(url_for("login"))
    role = request.form.get("role", "")
    item = next((entry for entry in EMPLOYEE_ROLES if entry["role"] == role), None)
    if not item:
        flash("Choose a valid employee role.", "danger")
        return redirect(url_for("game_dashboard"))
    user = current_user()
    name = request.form.get("name", "").strip() or role
    if not 2 <= len(name) <= 40:
        flash("Employee names must be 2–40 characters.", "danger")
        return redirect(url_for("game_dashboard"))
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM employees WHERE user_id=? AND role=?", (user["id"], role)).fetchone():
            flash("You have already hired this role.", "warning")
            return redirect(url_for("game_dashboard"))
        level = level_for(db.execute("SELECT xp FROM users WHERE id=?", (user["id"],)).fetchone()["xp"])
        if level < item["level"]:
            flash(f"This role unlocks at character level {item['level']}.", "warning")
            return redirect(url_for("game_dashboard"))
        if not db.execute("SELECT 1 FROM office_upgrades WHERE user_id=? AND upgrade_id=?", (user["id"], item["upgrade"])).fetchone():
            flash("Purchase the required workspace or department before hiring.", "warning")
            return redirect(url_for("game_dashboard"))
        debit = db.execute("UPDATE users SET coins=coins-? WHERE id=? AND coins>=?", (item["price"], user["id"], item["price"]))
        if debit.rowcount != 1:
            flash("Not enough coins to hire this employee.", "danger")
            return redirect(url_for("game_dashboard"))
        db.execute("INSERT INTO employees(user_id,role,name,hired_at) VALUES(?,?,?,?)",
                   (user["id"], role, name, utc_now().isoformat()))
        db.execute("INSERT INTO wallet_transactions(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
                   (user["id"], -item["price"], f"Hired {name} ({role})", utc_now().isoformat()))
        sync_game_progress(db, user["id"])
    flash(f"{name} joined your virtual team.", "success")
    return redirect(url_for("game_dashboard"))

@app.route("/game/boss/<boss_id>/step", methods=["POST"])
def submit_boss_step(boss_id):
    if not login_required(): return redirect(url_for("login"))
    boss = next((entry for entry in BOSS_BATTLES if entry["id"] == boss_id), None)
    if not boss:
        flash("Boss battle not found.", "danger")
        return redirect(url_for("game_dashboard"))
    answer = request.form.get("answer", "").strip()
    if len(answer) < 30 or len(answer) > 2000:
        flash("Battle answers must be 30–2,000 characters.", "warning")
        return redirect(url_for("game_dashboard"))
    user = current_user()
    submitted_at = utc_now().isoformat()
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        fresh_user = db.execute("SELECT xp FROM users WHERE id=?", (user["id"],)).fetchone()
        if level_for(fresh_user["xp"]) < boss["level"]:
            flash(f"This battle unlocks at character level {boss['level']}.", "warning")
            return redirect(url_for("game_dashboard"))
        progress = db.execute("SELECT * FROM boss_progress WHERE user_id=? AND boss_id=?", (user["id"], boss_id)).fetchone()
        if progress and progress["completed_at"]:
            flash("This boss battle is already complete.", "warning")
            return redirect(url_for("game_dashboard"))
        step = progress["current_step"] if progress else 0
        try:
            db.execute("INSERT INTO boss_answers(user_id,boss_id,step_number,answer,submitted_at) VALUES(?,?,?,?,?)",
                       (user["id"], boss_id, step, answer, submitted_at))
        except sqlite3.IntegrityError:
            flash("That battle step was already submitted.", "warning")
            return redirect(url_for("game_dashboard"))
        next_step = step + 1
        is_complete = next_step >= len(boss["steps"])
        db.execute(
            "INSERT INTO boss_progress(user_id,boss_id,current_step,completed_at) VALUES(?,?,?,?) "
            "ON CONFLICT(user_id,boss_id) DO UPDATE SET current_step=excluded.current_step,completed_at=excluded.completed_at",
            (user["id"], boss_id, next_step, submitted_at if is_complete else None)
        )
        if is_complete:
            old_level = level_for(db.execute("SELECT xp FROM users WHERE id=?", (user["id"],)).fetchone()["xp"])
            db.execute("UPDATE users SET xp=xp+?,coins=coins+? WHERE id=?", (boss["xp"], boss["coins"], user["id"]))
            new_level = level_for(db.execute("SELECT xp FROM users WHERE id=?", (user["id"],)).fetchone()["xp"])
            db.execute("UPDATE game_profiles SET startup_xp=startup_xp+?,startup_level=1+(startup_xp+?)/300 WHERE user_id=?",
                       (boss["xp"], boss["xp"], user["id"]))
            update_streak(db, user["id"], submitted_at)
            db.execute("INSERT INTO wallet_transactions(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
                       (user["id"], boss["coins"], f"Boss battle: {boss['name']}", submitted_at))
            sync_game_progress(db, user["id"])
    flash(
        f"Boss defeated! +{boss['xp']} XP and {boss['coins']} coins." +
        (f" Level up! Founder Level {new_level}." if new_level > old_level else "") if is_complete
        else f"Battle step {next_step} saved. Continue to the next objective.",
        "success"
    )
    return redirect(url_for("game_dashboard"))

@app.route("/missions")
def mission_board():
    if not login_required(): return redirect(url_for("login"))
    user = current_user()
    with connect_db() as db:
        rows = db.execute("SELECT mission_id,score FROM submissions WHERE user_id=?", (user["id"],)).fetchall()
    completed = {r["mission_id"]: r["score"] for r in rows}
    return render_template("missions.html", completed=completed, level=level_for(user["xp"]))

@app.route("/mission/<int:mission_id>", methods=["GET", "POST"])
def mission_detail(mission_id):
    if not login_required(): return redirect(url_for("login"))
    mission = next((m for m in MISSIONS if m["id"] == mission_id), None)
    if not mission:
        flash("Mission not found.", "danger")
        return redirect(url_for("mission_board"))
    user = current_user()
    if level_for(user["xp"]) < mission["unlock"]:
        flash(f"This mission unlocks at Level {mission['unlock']}. Keep completing missions!", "warning")
        return redirect(url_for("mission_board"))
    with connect_db() as db:
        existing = db.execute("SELECT * FROM submissions WHERE user_id=? AND mission_id=?", (user["id"], mission_id)).fetchone()
        has_research = db.execute("SELECT 1 FROM inventory WHERE user_id=? AND item_id='research'", (user["id"],)).fetchone()
    if request.method == "POST":
        if existing:
            flash("You've already completed this mission. Rewards are only granted once.", "warning")
            return redirect(url_for("mission_detail", mission_id=mission_id))
        answer = request.form.get("answer", "").strip()
        if len(answer) < 35:
            flash("Write at least 35 characters so your business idea has enough detail.", "warning")
            return render_template("mission.html", mission=mission, existing=None, has_research=has_research)
        score, feedback = score_answer(answer)
        multiplier = 1.15 if score >= 80 else 1.0
        xp_awarded = int(mission["xp"] * (0.5 + score / 200))
        coins_awarded = int(mission["coins"] * (0.5 + score / 200) * multiplier)
        feedback_text = "\n".join(feedback)
        leveled_up = False
        with connect_db() as db:
            db.execute("BEGIN IMMEDIATE")
            # UNIQUE(user_id, mission_id) prevents duplicate rewards for a mission.
            try:
                db.execute("INSERT INTO submissions(user_id,mission_id,answer,score,feedback,xp_awarded,coins_awarded,created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (user["id"], mission_id, answer, score, feedback_text, xp_awarded, coins_awarded, utc_now().isoformat()))
                old_level = level_for(db.execute("SELECT xp FROM users WHERE id=?", (user["id"],)).fetchone()["xp"])
                db.execute("UPDATE users SET xp=xp+?, coins=coins+? WHERE id=?", (xp_awarded, coins_awarded, user["id"]))
                new_level = level_for(db.execute("SELECT xp FROM users WHERE id=?", (user["id"],)).fetchone()["xp"])
                leveled_up = new_level > old_level
                db.execute("UPDATE game_profiles SET startup_xp=startup_xp+?, startup_level=1+(startup_xp+?)/300 WHERE user_id=?",
                    (xp_awarded, xp_awarded, user["id"]))
                update_streak(db, user["id"], utc_now().isoformat())
                db.execute("INSERT INTO wallet_transactions(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
                    (user["id"], coins_awarded, f"Mission reward: {mission['title']}", utc_now().isoformat()))
                sync_game_progress(db, user["id"])
            except sqlite3.IntegrityError:
                flash("This mission has already been submitted.", "warning")
                return redirect(url_for("mission_detail", mission_id=mission_id))
        if leveled_up:
            flash(f"Level up! You reached Founder Level {new_level}.", "success")
        return redirect(url_for("results", mission_id=mission_id))
    return render_template("mission.html", mission=mission, existing=existing, has_research=has_research)

@app.route("/results/<int:mission_id>")
def results(mission_id):
    if not login_required(): return redirect(url_for("login"))
    user = current_user()
    mission = next((m for m in MISSIONS if m["id"] == mission_id), None)
    with connect_db() as db:
        result = db.execute("SELECT * FROM submissions WHERE user_id=? AND mission_id=?", (user["id"], mission_id)).fetchone()
    if not mission or not result:
        flash("No result found for that mission.", "warning")
        return redirect(url_for("mission_board"))
    return render_template("results.html", mission=mission, result=result, feedback=result["feedback"].splitlines())

@app.route("/shop")
def shop():
    if not login_required(): return redirect(url_for("login"))
    user = current_user()
    with connect_db() as db:
        rows = db.execute("SELECT item_id FROM inventory WHERE user_id=?", (user["id"],)).fetchall()
    owned_ids = {r["item_id"] for r in rows}
    return render_template("shop.html", owned_ids=owned_ids)

@app.route("/buy/<item_id>", methods=["POST"])
def buy_item(item_id):
    if not login_required(): return redirect(url_for("login"))
    item = next((i for i in SHOP_ITEMS if i["id"] == item_id), None)
    if not item:
        flash("Item not found.", "danger")
        return redirect(url_for("shop"))
    user = current_user()
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM inventory WHERE user_id=? AND item_id=?", (user["id"], item_id)).fetchone():
            flash("You already own this item.", "warning")
            return redirect(url_for("shop"))
        fresh_user = db.execute("SELECT coins FROM users WHERE id=?", (user["id"],)).fetchone()
        if fresh_user["coins"] < item["price"]:
            flash("Not enough coins yet. Complete another mission to earn more.", "danger")
            return redirect(url_for("shop"))
        debit = db.execute("UPDATE users SET coins=coins-? WHERE id=? AND coins>=?", (item["price"], user["id"], item["price"]))
        if debit.rowcount != 1:
            flash("Not enough coins yet. Complete another mission to earn more.", "danger")
            return redirect(url_for("shop"))
        db.execute("INSERT INTO inventory(user_id,item_id,purchased_at) VALUES(?,?,?)",
            (user["id"], item_id, utc_now().isoformat()))
        db.execute("INSERT INTO wallet_transactions(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
            (user["id"], -item["price"], f"Purchased {item['name']}", utc_now().isoformat()))
    flash(f"{item['name']} added to your inventory!", "success")
    return redirect(url_for("shop"))

@app.route("/profile")
def profile():
    if not login_required(): return redirect(url_for("login"))
    user = current_user()
    with connect_db() as db:
        inventory = db.execute("SELECT item_id FROM inventory WHERE user_id=?", (user["id"],)).fetchall()
        transactions = db.execute("SELECT * FROM wallet_transactions WHERE user_id=? ORDER BY id DESC LIMIT 10", (user["id"],)).fetchall()
        submissions = db.execute("SELECT * FROM submissions WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    items = {i["id"]: i for i in SHOP_ITEMS}
    return render_template("profile.html", user=user, inventory=[items[r["item_id"]] for r in inventory if r["item_id"] in items],
        transactions=transactions, submissions=submissions)

def ml_csrf_token():
    token = session.get("ml_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["ml_csrf_token"] = token
    return token

def ml_dataset_version():
    try:
        return ml_lab.dataset_fingerprint()
    except ml_lab.MLLabError:
        return "unavailable"

def valid_ml_csrf():
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    expected = session.get("ml_csrf_token", "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))

def award_ml_quests(db, user_id, event):
    claimed = []
    now = utc_now().isoformat()
    for quest in ml_lab.ML_QUESTS:
        if quest["event"] != event:
            continue
        inserted = db.execute(
            "INSERT OR IGNORE INTO ml_quest_claims(user_id,quest_id,claimed_at) VALUES(?,?,?)",
            (user_id, quest["id"], now)
        )
        if inserted.rowcount != 1:
            continue
        rewards = MISSION_REWARDS[quest["difficulty"]]
        db.execute(
            "UPDATE users SET xp=xp+?,coins=coins+? WHERE id=?",
            (rewards["xp"], rewards["coins"], user_id)
        )
        db.execute(
            "UPDATE game_profiles SET startup_xp=startup_xp+?,startup_level=1+(startup_xp+?)/300 WHERE user_id=?",
            (rewards["xp"], rewards["xp"], user_id)
        )
        update_streak(db, user_id, now)
        db.execute(
            "INSERT INTO wallet_transactions(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
            (user_id, rewards["coins"], f"ML Research quest: {quest['title']}", now)
        )
        sync_game_progress(db, user_id)
        claimed.append(
            {"title": quest["title"], "xp": rewards["xp"], "coins": rewards["coins"]}
        )
    return claimed

@app.route("/ml-lab")
def ml_lab_page():
    if not login_required(): return redirect(url_for("login"))
    user = current_user()
    catalog = []
    selected_dataset = request.args.get("dataset", "Synthetic_Sales_Demo")
    exploration = None
    catalog_error = None
    try:
        catalog = ml_lab.dataset_catalog()
        trainable = {entry["name"] for entry in catalog if entry["trainable"]}
        if selected_dataset not in {entry["name"] for entry in catalog}:
            selected_dataset = "Synthetic_Sales_Demo"
        exploration = ml_lab.explore_dataset(selected_dataset)
    except ml_lab.MLLabError as error:
        catalog_error = str(error)
    with connect_db() as db:
        experiments = db.execute(
            "SELECT * FROM ml_experiments WHERE user_id=? ORDER BY created_at DESC LIMIT 30",
            (user["id"],)
        ).fetchall()
        claims = db.execute(
            "SELECT quest_id FROM ml_quest_claims WHERE user_id=?", (user["id"],)
        ).fetchall()
        predictions = db.execute(
            "SELECT p.*,e.dataset_name,e.algorithm,e.metrics_json FROM ml_predictions p "
            "JOIN ml_experiments e ON e.id=p.experiment_id WHERE p.user_id=? "
            "ORDER BY p.created_at DESC LIMIT 8",
            (user["id"],)
        ).fetchall()
        comparison_rows = db.execute(
            "SELECT * FROM ml_model_comparisons WHERE user_id=? ORDER BY created_at DESC LIMIT 8",
            (user["id"],)
        ).fetchall()
    claimed_quests = {row["quest_id"] for row in claims}
    experiment_rows = []
    for row in experiments:
        item = dict(row)
        item["metrics"] = json.loads(item["metrics_json"])
        item["features"] = json.loads(item["feature_columns"])
        item["config"] = json.loads(item["config_json"])
        experiment_rows.append(item)
    selected_experiment = None
    selected_id = request.args.get("experiment", "")
    if selected_id:
        selected_experiment = next(
            (row for row in experiment_rows if row["id"] == selected_id), None
        )
    if not selected_experiment and experiment_rows:
        selected_experiment = experiment_rows[0]
    prediction_specs = []
    if selected_experiment and selected_experiment["status"] in {"trained", "saved"}:
        try:
            prediction_specs = ml_lab.prediction_features(
                selected_experiment["dataset_name"], selected_experiment["features"]
            )
        except ml_lab.MLLabError:
            prediction_specs = []
    prediction_rows = []
    for row in predictions:
        item = dict(row)
        item["result"] = json.loads(item["result_json"])
        prediction_rows.append(item)
    comparisons = []
    for row in comparison_rows:
        item = dict(row)
        item["metrics"] = json.loads(item["metrics_json"])
        comparisons.append(item)
    return render_template(
        "ml_lab.html",
        catalog=catalog,
        selected_dataset=selected_dataset,
        exploration=exploration,
        catalog_error=catalog_error,
        experiments=experiment_rows,
        selected_experiment=selected_experiment,
        prediction_specs=prediction_specs,
        predictions=prediction_rows,
        comparisons=comparisons,
        ml_quests=ml_lab.ML_QUESTS,
        claimed_quests=claimed_quests,
        csrf_token=ml_csrf_token(),
        algorithm_labels=ml_lab.ALGORITHM_LABELS,
        rewards=MISSION_REWARDS,
        selected_prediction=request.args.get("prediction", ""),
    )

@app.route("/ml-lab/explore", methods=["POST"])
def ml_lab_explore():
    if not login_required(): return redirect(url_for("login"))
    if not valid_ml_csrf():
        flash("Your research session expired. Reload the ML Lab and try again.", "danger")
        return redirect(url_for("ml_lab_page"))
    dataset_name = request.form.get("dataset", "")
    try:
        ml_lab.explore_dataset(dataset_name)
    except ml_lab.MLLabError as error:
        flash(str(error), "danger")
        return redirect(url_for("ml_lab_page"))
    user = current_user()
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT OR IGNORE INTO ml_dataset_explorations(user_id,dataset_name,explored_at) VALUES(?,?,?)",
            (user["id"], dataset_name, utc_now().isoformat())
        )
        claimed = award_ml_quests(db, user["id"], "explore")
    flash(
        "Dataset loaded from the supplied workbook."
        + (f" Research quest complete: {claimed[0]['title']}." if claimed else ""),
        "success",
    )
    return redirect(url_for("ml_lab_page", dataset=dataset_name))

@app.route("/ml-lab/chart", methods=["POST"])
def ml_lab_chart():
    if not login_required(): return jsonify({"error": "Sign in to use the Research Lab."}), 401
    if not valid_ml_csrf():
        return jsonify({"error": "Research session expired. Reload the page and retry."}), 400
    payload = request.get_json(silent=True) or {}
    try:
        chart = ml_lab.chart_data(payload.get("dataset", ""), payload.get("column", ""))
    except ml_lab.MLLabError as error:
        return jsonify({"error": str(error)}), 400
    user = current_user()
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        claimed = award_ml_quests(db, user["id"], "analysis")
    chart["quest_rewards"] = claimed
    return jsonify(chart)

@app.route("/ml-lab/train", methods=["POST"])
def ml_lab_train():
    if not login_required(): return redirect(url_for("login"))
    if not valid_ml_csrf():
        flash("Your research session expired. Reload the ML Lab and try again.", "danger")
        return redirect(url_for("ml_lab_page"))
    user = current_user()
    dataset_name = request.form.get("dataset", "")
    task = request.form.get("task", "")
    target = request.form.get("target", "")
    algorithm = request.form.get("algorithm", "")
    features = request.form.getlist("features")
    parameters = {
        "n_estimators": request.form.get("n_estimators", "100"),
        "max_depth": request.form.get("max_depth", ""),
        "n_clusters": request.form.get("n_clusters", "3"),
    }
    test_size = request.form.get("test_size", "0.2")
    experiment_id = uuid.uuid4().hex
    artifact_id = uuid.uuid4().hex
    try:
        if dataset_name not in ml_lab.DATASET_META:
            raise ml_lab.MLLabError("Select one of the three included synthetic datasets.")
        result = ml_lab.train_model(
            dataset_name, task, target, features, algorithm, parameters, test_size
        )
        artifact = ml_lab.save_artifact(result["pipeline"], artifact_id)
        metrics = {
            "scores": result["metrics"],
            "warnings": result["warnings"],
            "chart": result["chart"],
            "train_rows": result["train_rows"],
            "test_rows": result["test_rows"],
            "split_date_range": result.get("split_date_range"),
        }
        config = {
            "parameters": parameters,
            "test_size": float(test_size),
            "random_seed": 42,
            "model_version": 1,
            "chronological": result.get("chronological", False),
        }
        now = utc_now().isoformat()
        with connect_db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO ml_experiments(id,user_id,dataset_name,dataset_version,dataset_origin,task,target_column,"
                "feature_columns,algorithm,metrics_json,config_json,status,artifact_id,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    experiment_id, user["id"], dataset_name, ml_lab.dataset_fingerprint(),
                    ml_lab.DATASET_META[dataset_name]["origin"], task, result["target"],
                    ml_lab.encode_json(result["features"]), algorithm,
                    ml_lab.encode_json(metrics), ml_lab.encode_json(config), "trained",
                    artifact_id, now,
                ),
            )
            events = []
            if task in {"regression", "classification"}:
                events.append(task)
            if result["metrics"]:
                events.append("evaluation")
            rewards = []
            for event in events:
                rewards.extend(award_ml_quests(db, user["id"], event))
        status_message = (
            f"Model trained and evaluated using {result['train_rows']:,} training rows "
            f"and {result['test_rows']:,} test rows. A private model artifact is ready."
        )
        if rewards:
            status_message += " Quest rewards: " + ", ".join(
                f"{item['title']} (+{item['xp']} XP, +{item['coins']} coins)"
                for item in rewards
            )
        flash(status_message, "success")
    except ml_lab.MLLabError as error:
        with connect_db() as db:
            db.execute(
                "INSERT INTO ml_experiments(id,user_id,dataset_name,dataset_version,dataset_origin,task,target_column,"
                "feature_columns,algorithm,metrics_json,config_json,status,error_message,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,'{}','{}','failed',?,?)",
                (
                    experiment_id, user["id"], dataset_name[:100] or "unknown",
                    ml_dataset_version(), ml_lab.DATASET_META.get(dataset_name, {}).get("origin", "Unknown"),
                    task if task in {"regression", "classification", "clustering"} else "regression",
                    target[:200], ml_lab.encode_json(features[:20]), algorithm[:100] or "unknown",
                    str(error)[:500], utc_now().isoformat(),
                ),
            )
        flash(f"Training failed: {error}", "danger")
        return redirect(url_for("ml_lab_page", dataset=dataset_name if dataset_name in ml_lab.DATASET_META else "Synthetic_Sales_Demo", experiment=experiment_id))
    except (ValueError, TypeError, OSError) as error:
        app.logger.warning("ML experiment %s failed: %s", experiment_id, error)
        with connect_db() as db:
            db.execute(
                "INSERT INTO ml_experiments(id,user_id,dataset_name,dataset_version,dataset_origin,task,target_column,"
                "feature_columns,algorithm,metrics_json,config_json,status,error_message,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,'{}','{}','failed',?,?)",
                (
                    experiment_id, user["id"], dataset_name[:100] or "unknown",
                    ml_dataset_version(), ml_lab.DATASET_META.get(dataset_name, {}).get("origin", "Unknown"),
                    task if task in {"regression", "classification", "clustering"} else "regression",
                    target[:200], ml_lab.encode_json(features[:20]), algorithm[:100] or "unknown",
                    "The selected model could not be trained with these settings.", utc_now().isoformat(),
                ),
            )
        flash("Training could not complete with those settings. Check the selected target, features, and parameters.", "danger")
        return redirect(url_for("ml_lab_page", dataset=dataset_name if dataset_name in ml_lab.DATASET_META else "Synthetic_Sales_Demo", experiment=experiment_id))
    return redirect(url_for("ml_lab_page", dataset=dataset_name, experiment=experiment_id))

@app.route("/ml-lab/models/<experiment_id>/save", methods=["POST"])
def ml_lab_save_model(experiment_id):
    if not login_required(): return redirect(url_for("login"))
    if not valid_ml_csrf():
        flash("Your research session expired. Reload the ML Lab and try again.", "danger")
        return redirect(url_for("ml_lab_page"))
    user = current_user()
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        model = db.execute(
            "SELECT * FROM ml_experiments WHERE id=? AND user_id=?",
            (experiment_id, user["id"])
        ).fetchone()
        if not model or model["status"] not in {"trained", "saved"}:
            flash("That trained model is unavailable.", "danger")
            return redirect(url_for("ml_lab_page"))
        artifact_path = os.path.join(str(ml_lab.ARTIFACT_DIR), f"{model['artifact_id']}.joblib") if model["artifact_id"] else ""
        if not artifact_path or not os.path.isfile(artifact_path):
            flash("The private model artifact is missing; train the model again.", "danger")
            return redirect(url_for("ml_lab_page", dataset=model["dataset_name"]))
        updated = db.execute(
            "UPDATE ml_experiments SET status='saved' WHERE id=? AND user_id=? AND status='trained'",
            (experiment_id, user["id"])
        )
        rewards = award_ml_quests(db, user["id"], "save") if updated.rowcount else []
    flash("Model saved to your private collection." + (
        f" Research quest complete: {rewards[0]['title']}." if rewards else " It was already saved."
    ), "success")
    return redirect(url_for("ml_lab_page", dataset=model["dataset_name"], experiment=experiment_id))

@app.route("/ml-lab/compare", methods=["POST"])
def ml_lab_compare():
    if not login_required(): return redirect(url_for("login"))
    if not valid_ml_csrf():
        flash("Your research session expired. Reload the ML Lab and try again.", "danger")
        return redirect(url_for("ml_lab_page"))
    experiment_ids = request.form.getlist("experiments")
    if len(experiment_ids) != 2 or experiment_ids[0] == experiment_ids[1]:
        flash("Choose two different successful experiments to compare.", "warning")
        return redirect(url_for("ml_lab_page", _anchor="experiments"))
    user = current_user()
    ordered_ids = sorted(experiment_ids)
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute(
            "SELECT * FROM ml_experiments WHERE user_id=? AND id IN (?,?) "
            "AND status IN ('trained','saved')",
            (user["id"], *experiment_ids)
        ).fetchall()
        if len(rows) != 2:
            flash("One or both experiments are unavailable.", "danger")
            return redirect(url_for("ml_lab_page", _anchor="experiments"))
        by_id = {row["id"]: row for row in rows}
        left, right = by_id[ordered_ids[0]], by_id[ordered_ids[1]]
        if (
            left["dataset_name"] != right["dataset_name"]
            or left["dataset_version"] != right["dataset_version"]
            or left["task"] != right["task"]
            or left["target_column"] != right["target_column"]
        ):
            flash(
                "Compare models trained on the same dataset version, task, and target so their held-out metrics are comparable.",
                "warning",
            )
            return redirect(url_for("ml_lab_page", _anchor="experiments"))
        left_metrics = json.loads(left["metrics_json"]).get("scores", {})
        right_metrics = json.loads(right["metrics_json"]).get("scores", {})
        if not left_metrics or not right_metrics:
            flash("Both experiments must have real evaluation metrics.", "warning")
            return redirect(url_for("ml_lab_page", _anchor="experiments"))
        comparison = {
            "task": left["task"],
            "dataset": left["dataset_name"],
            "target": left["target_column"],
            "models": [
                {
                    "experiment_id": item["id"],
                    "algorithm": item["algorithm"],
                    "metrics": score,
                }
                for item, score in ((left, left_metrics), (right, right_metrics))
            ],
        }
        db.execute(
            "INSERT OR IGNORE INTO ml_model_comparisons(id,user_id,left_experiment_id,right_experiment_id,metrics_json,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (
                uuid.uuid4().hex, user["id"], left["id"], right["id"],
                ml_lab.encode_json(comparison), utc_now().isoformat(),
            ),
        )
        rewards = award_ml_quests(db, user["id"], "compare")
    flash(
        "Held-out model metrics compared."
        + (f" Research quest complete: {rewards[0]['title']}." if rewards else ""),
        "success",
    )
    return redirect(url_for("ml_lab_page", experiment=right["id"], dataset=right["dataset_name"], _anchor="experiments"))

@app.route("/ml-lab/models/<experiment_id>/predict", methods=["POST"])
def ml_lab_predict(experiment_id):
    if not login_required(): return redirect(url_for("login"))
    if not valid_ml_csrf():
        flash("Your research session expired. Reload the ML Lab and try again.", "danger")
        return redirect(url_for("ml_lab_page"))
    user = current_user()
    with connect_db() as db:
        model = db.execute(
            "SELECT * FROM ml_experiments WHERE id=? AND user_id=? AND status IN ('trained','saved')",
            (experiment_id, user["id"])
        ).fetchone()
    if not model:
        flash("That model is unavailable.", "danger")
        return redirect(url_for("ml_lab_page"))
    try:
        specs = ml_lab.prediction_features(model["dataset_name"], json.loads(model["feature_columns"]))
        values = {spec["name"]: request.form.get(f"feature:{spec['name']}", "") for spec in specs}
        pipeline = ml_lab.load_artifact(model["artifact_id"])
        result = ml_lab.predict(pipeline, specs, values)
    except ml_lab.MLLabError as error:
        flash(str(error), "danger")
        return redirect(url_for("ml_lab_page", dataset=model["dataset_name"], experiment=experiment_id))
    prediction_id = uuid.uuid4().hex
    with connect_db() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT INTO ml_predictions(id,user_id,experiment_id,result_json,created_at) VALUES(?,?,?,?,?)",
            (prediction_id, user["id"], experiment_id, ml_lab.encode_json(result), utc_now().isoformat())
        )
        rewards = award_ml_quests(db, user["id"], "prediction")
    flash("Prediction calculated by your saved pipeline." + (
        f" Research quest complete: {rewards[0]['title']}." if rewards else ""
    ), "success")
    return redirect(url_for(
        "ml_lab_page", dataset=model["dataset_name"], experiment=experiment_id, prediction=prediction_id
    ))

if __name__ == "__main__":
    app.run(debug=True)
