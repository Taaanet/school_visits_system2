from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='supervisor')  # admin, supervisor, teacher
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    # دالة للبحث عن المستخدم بالبريد الإلكتروني أو اسم المستخدم
    @classmethod
    def find_user(cls, identifier):
        return cls.query.filter((cls.username == identifier) | (cls.email == identifier)).first()

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    school = db.Column(db.String(100), nullable=False)

class Supervisor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    specialty = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))

class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    visit_date = db.Column(db.DateTime, nullable=False)
    school_name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    supervisor_id = db.Column(db.Integer, db.ForeignKey('supervisor.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.String(50), nullable=False)
    lesson_title = db.Column(db.String(200), nullable=False)
    
    # Evaluation scores
    management_scores = db.Column(db.JSON)  # Stores scores for management criteria
    teaching_scores = db.Column(db.JSON)    # Stores scores for teaching criteria
    feedback_scores = db.Column(db.JSON)    # Stores scores for feedback criteria
    
    # Feedback and recommendations
    feedback_1 = db.Column(db.Text)
    feedback_2 = db.Column(db.Text)
    suggestions = db.Column(db.Text)
    follow_up_date = db.Column(db.DateTime)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='مكتملة')  # مكتملة, معلقة, ملغاة
    supervisor_signature = db.Column(db.String(100))
    
    # Relationships
    teacher = db.relationship('Teacher', backref=db.backref('visits', lazy=True))
    supervisor = db.relationship('Supervisor', backref=db.backref('visits', lazy=True))