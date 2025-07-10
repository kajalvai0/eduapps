from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from datetime import date, datetime, timedelta
from typing import Optional, List
from sqlmodel import SQLModel, Field, Session, create_engine, select
import os
import shutil

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database.db")

engine = create_engine(DATABASE_URL, echo=False)

# -----------------------------
# Database Models
# -----------------------------
class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    class_name: str  # e.g. "৯ম" / "10"
    roll: int
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    date_of_birth: Optional[date] = None
    admission_date: date = Field(default_factory=date.today)

class Teacher(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    subject: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    date_of_joining: date = Field(default_factory=date.today)

class Attendance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    date: date
    status: str  # "Present" / "Absent"

class Result(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    subject: str
    marks: float
    exam_date: date

class Notice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UploadedFile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    original_filename: str
    stored_filename: str
    upload_date: datetime = Field(default_factory=datetime.utcnow)

# -----------------------------
# Utility functions
# -----------------------------

def get_session():
    with Session(engine) as session:
        yield session

# Ensure uploads directory exists
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Security settings
SECRET_KEY = os.getenv("SECRET_KEY", "shibganj_islamic_academy_secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class Token(BaseModel):
    access_token: str
    token_type: str

# -----------------------------
# User model (for admin authentication)
# -----------------------------
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, nullable=False)
    hashed_password: str
    full_name: Optional[str] = None

# Password utilities

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Dependency to get current user

def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)) -> User:
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise credentials_exception
    return user

# -----------------------------
# FastAPI App
# -----------------------------
app = FastAPI(title="Shibganj Islamic Academy API", version="1.0.0")

# CORS for front-end access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files
app.mount("/files", StaticFiles(directory=UPLOAD_DIR), name="files")

# -----------------------------
# Startup: create DB tables
# -----------------------------
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

# -----------------------------
# Auth endpoints
# -----------------------------
@app.post("/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# -----------------------------
# Ensure default admin on startup
# -----------------------------
@app.on_event("startup")
def create_admin():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        admin_exists = session.exec(select(User).where(User.username == "admin")).first()
        if not admin_exists:
            admin = User(username="admin", hashed_password=get_password_hash("admin123"), full_name="Administrator")
            session.add(admin)
            session.commit()

# -----------------------------
# Student Endpoints
# -----------------------------
@app.post("/students", response_model=Student)
def add_student(student: Student, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    session.add(student)
    session.commit()
    session.refresh(student)
    return student

@app.get("/students", response_model=List[Student])
def list_students(session: Session = Depends(get_session)):
    students = session.exec(select(Student)).all()
    return students

@app.get("/students/{student_id}", response_model=Student)
def get_student(student_id: int, session: Session = Depends(get_session)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

@app.put("/students/{student_id}", response_model=Student)
def update_student(student_id: int, student_data: Student, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    student_data.id = student_id
    session.merge(student_data)
    session.commit()
    return student_data

@app.delete("/students/{student_id}")
def delete_student(student_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    session.delete(student)
    session.commit()
    return {"deleted": True}

# -----------------------------
# Teacher Endpoints
# -----------------------------
@app.post("/teachers", response_model=Teacher)
def add_teacher(teacher: Teacher, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    session.add(teacher)
    session.commit()
    session.refresh(teacher)
    return teacher

@app.get("/teachers", response_model=List[Teacher])
def list_teachers(session: Session = Depends(get_session)):
    return session.exec(select(Teacher)).all()

@app.get("/teachers/{teacher_id}", response_model=Teacher)
def get_teacher(teacher_id: int, session: Session = Depends(get_session)):
    teacher = session.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return teacher

@app.put("/teachers/{teacher_id}", response_model=Teacher)
def update_teacher(teacher_id: int, teacher_data: Teacher, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    teacher_data.id = teacher_id
    session.merge(teacher_data)
    session.commit()
    return teacher_data

@app.delete("/teachers/{teacher_id}")
def delete_teacher(teacher_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    teacher = session.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    session.delete(teacher)
    session.commit()
    return {"deleted": True}

# -----------------------------
# Attendance Endpoints
# -----------------------------
@app.post("/attendance", response_model=Attendance)
def mark_attendance(record: Attendance, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    # optional: uniqueness check per student+date
    existing = session.exec(select(Attendance).where(Attendance.student_id == record.student_id, Attendance.date == record.date)).first()
    if existing:
        existing.status = record.status
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    session.add(record)
    session.commit()
    session.refresh(record)
    return record

@app.get("/attendance/student/{student_id}", response_model=List[Attendance])
def get_attendance(student_id: int, session: Session = Depends(get_session)):
    return session.exec(select(Attendance).where(Attendance.student_id == student_id)).all()

# -----------------------------
# Results Endpoints
# -----------------------------
@app.post("/results", response_model=Result)
def add_result(result: Result, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    session.add(result)
    session.commit()
    session.refresh(result)
    return result

@app.get("/results/student/{student_id}", response_model=List[Result])
def get_results(student_id: int, session: Session = Depends(get_session)):
    return session.exec(select(Result).where(Result.student_id == student_id)).all()

# -----------------------------
# Notice Endpoints (Dynamic Content)
# -----------------------------
@app.post("/notices", response_model=Notice)
def create_notice(notice: Notice, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    session.add(notice)
    session.commit()
    session.refresh(notice)
    return notice

@app.get("/notices", response_model=List[Notice])
def list_notices(session: Session = Depends(get_session)):
    return session.exec(select(Notice).order_by(Notice.created_at.desc())).all()

@app.get("/notices/{notice_id}", response_model=Notice)
def get_notice(notice_id: int, session: Session = Depends(get_session)):
    notice = session.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
    return notice

@app.put("/notices/{notice_id}", response_model=Notice)
def update_notice(notice_id: int, notice_data: Notice, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    notice_data.id = notice_id
    session.merge(notice_data)
    session.commit()
    return notice_data

@app.delete("/notices/{notice_id}")
def delete_notice(notice_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    notice = session.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
    session.delete(notice)
    session.commit()
    return {"deleted": True}

# -----------------------------
# File Upload Endpoint
# -----------------------------
@app.post("/upload", response_model=UploadedFile)
async def upload_file(file: UploadFile = File(...), session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    stored_name = f"{int(datetime.utcnow().timestamp())}_{file.filename}"
    destination = os.path.join(UPLOAD_DIR, stored_name)
    with open(destination, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    upload_entry = UploadedFile(original_filename=file.filename, stored_filename=stored_name)
    session.add(upload_entry)
    session.commit()
    session.refresh(upload_entry)
    return upload_entry

# Health check
@app.get("/")
def root():
    return {"message": "Shibganj Islamic Academy API is running"}

# -----------------------------
# Run via `uvicorn backend.main:app --reload`
# -----------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)