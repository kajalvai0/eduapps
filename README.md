# eduapps

## Backend API

### Setup
```bash
# Create virtual environment (optional)
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn backend.main:app --reload
```

The API docs will be available at `http://localhost:8000/docs`.

### Features
1. Students CRUD (`/students`)
2. Teachers CRUD (`/teachers`)
3. Attendance tracking (`/attendance`)
4. Results management (`/results`)
5. Notice / dynamic content (`/notices`)
6. File uploads (`/upload`) — uploaded files served from `/files/{filename}`

SQLite database file `database.db` is created automatically.

### Authentication
A default admin user is created automatically:

```
username: admin
password: admin123
```

Obtain token:
```
POST /auth/login (form-urlencoded)
  - username
  - password
```
Use the returned `access_token` as HTTP header:
```
Authorization: Bearer <token>
```

---