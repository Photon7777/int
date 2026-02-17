🧠 Internship Application Agent

Generate tailored internship application materials and maintain a private job tracker — per user.

Built with Streamlit + SQLite + bcrypt authentication.

🚀 Features
🧾 Application Pack Generator

Upload resume (PDF or TXT)

Paste job description or job URL

AI-generated tailored application materials

Download as .txt or .docx

Optional auto-logging into tracker

📌 Private Job Tracker (Per User)

Secure login & signup

Independent tracker for every user

Add / edit / delete jobs inline

Status filters + search

Overview metrics (Applied, Interviews, Offers)

Upcoming follow-ups panel

CSV + Excel export

CSV import (merge or replace)

De-duplication logic

🔐 Authentication System

Secure password hashing with bcrypt

Change password

Delete account (wipes tracker)

SQLite storage

🛡️ Admin Panel

Admin users (configured via secrets.toml) can:

View all registered users

See job counts

View any user's tracker (read-only)

🏗️ Project Structure
.
├── app.py              # Main Streamlit UI
├── auth.py             # Authentication logic (bcrypt + users table)
├── db_store.py         # Tracker database logic (SQLite)
├── agent.py            # AI application pack generation
├── autofill.py         # Extract company/role/location from job post
├── tools.py            # Helper utilities
├── tracker.db          # SQLite database (auto-created, NOT committed)
├── .streamlit/
│   └── secrets.toml    # Admin config (NOT committed)
└── README.md
⚙️ Local Setup
1️⃣ Clone the repo
git clone https://github.com/YOUR_USERNAME/internship-agent.git
cd internship-agent
2️⃣ Create virtual environment
python -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows
3️⃣ Install dependencies
pip install -r requirements.txt

If you don't have a requirements.txt, generate one:

pip freeze > requirements.txt
4️⃣ Configure Admin Users (Optional)

Create:

.streamlit/secrets.toml

Add:

admin_users = ["your_username"]

⚠️ Do NOT commit this file. It is ignored via .gitignore.

5️⃣ Run the App
streamlit run app.py

App runs at:

http://localhost:8501
🗄️ Database

SQLite file: tracker.db

Auto-created on first run

Contains:

users table

applications table

Each tracker row is scoped to user_id.

🔐 Security Notes

Passwords are hashed with bcrypt

Each user has isolated tracker data

Admin access controlled via secrets.toml

tracker.db and secrets.toml are excluded from Git

🌍 Deployment Options

Recommended platforms:

Streamlit Community Cloud

Render

Railway

Fly.io

Make sure environment includes:

Python 3.9+

SQLite support

bcrypt

streamlit

📊 Tech Stack

Python

Streamlit

SQLite

Pandas

bcrypt

OpenPyXL

python-docx

PyPDF

🧩 Future Improvements

OAuth (Google login)

Email verification

Multi-role admin permissions

Interview analytics dashboard

Cloud-hosted database (Postgres)

👤 Author

Built by Sai Praneeth Kathi Moksha Gnana
MS Information Systems — University of Maryland
Aspiring Data / Analytics Engineer