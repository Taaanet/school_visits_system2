from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
import json
import socket
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'your-super-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///school_visits.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Define Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='supervisor')
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @classmethod
    def find_user(cls, identifier):
        return cls.query.filter((cls.username == identifier) | (cls.email == identifier)).first()
    
    # Required properties for Flask-Login
    def get_id(self):
        return str(self.id)
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    school = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.String(100))

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
    
    # Evaluation scores (stored as JSON strings)
    management_scores = db.Column(db.Text)
    teaching_scores = db.Column(db.Text)
    feedback_scores = db.Column(db.Text)
    
    # Feedback and recommendations
    feedback_1 = db.Column(db.Text)
    feedback_2 = db.Column(db.Text)
    suggestions = db.Column(db.Text)
    follow_up_date = db.Column(db.DateTime)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='مكتملة')
    supervisor_signature = db.Column(db.String(100))
    
    # Relationships
    teacher = db.relationship('Teacher', backref=db.backref('visits', lazy=True))
    supervisor = db.relationship('Supervisor', backref=db.backref('visits', lazy=True))

# Login manager user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Role-based access control decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('غير مصرح لك بالوصول إلى هذه الصفحة')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Email sending function
def send_visit_report_email(teacher_email, teacher_name, visit_date, supervisor_name, visit_id):
    """
    Send visit report email to teacher with PDF attachment
    """
    try:
        # Email settings
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        email_user = os.environ.get('EMAIL_USER', '')
        email_password = os.environ.get('EMAIL_PASSWORD', '')
        
        if not email_user or not email_password:
            return False
            
        # Create message
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = teacher_email
        msg['Subject'] = f"تقرير زيارة صفية - {teacher_name} - {visit_date}"
        
        # Email content
        body = f"""
        السلام عليكم ورحمة الله وبركاته
        
        سيادة المعلم/ة {teacher_name}
        
        تمت زيارة صفكم بتاريخ {visit_date} من قبل المشرف/ة {supervisor_name}.
        يرجى الاطلاع على التقرير الكامل المرفق.
        
        مع خالص التقدير،
        إدارة النظام
        """
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Generate PDF and attach it
        visit = Visit.query.get(visit_id)
        if visit:
            pdf_buffer = generate_pdf_buffer(visit)
            attachment = MIMEApplication(pdf_buffer.getvalue(), _subtype="pdf")
            attachment.add_header('Content-Disposition', 'attachment', filename=f"تقرير_زيارة_{visit_id}.pdf")
            msg.attach(attachment)
        
        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_user, email_password)
        text = msg.as_string()
        server.sendmail(email_user, teacher_email, text)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def generate_pdf_buffer(visit):
    """Generate PDF buffer for email attachment"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    title = Paragraph("تقرير زيارة مدرسية", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 0.5*inch))
    
    # Visit information
    visit_data = [
        ["المدرسة:", visit.school_name],
        ["التاريخ:", visit.visit_date.strftime('%Y-%m-%d')],
        ["المعلم:", visit.teacher.name],
        ["المشرف:", visit.supervisor.name],
        ["المادة:", visit.subject],
        ["الصف:", visit.grade],
        ["عنوان الدرس:", visit.lesson_title],
        ["حالة الزيارة:", visit.status]
    ]
    
    visit_table = Table(visit_data, colWidths=[1.5*inch, 4*inch])
    visit_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(visit_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Feedback
    if visit.feedback_1:
        feedback_title = Paragraph("التغذية الراجعة:", styles['Heading2'])
        elements.append(feedback_title)
        feedback_text = Paragraph(visit.feedback_1, styles['BodyText'])
        elements.append(feedback_text)
        elements.append(Spacer(1, 0.2*inch))
    
    if visit.feedback_2:
        feedback2_title = Paragraph("التغذية الراجعة الإضافية:", styles['Heading2'])
        elements.append(feedback2_title)
        feedback2_text = Paragraph(visit.feedback_2, styles['BodyText'])
        elements.append(feedback2_text)
        elements.append(Spacer(1, 0.2*inch))
    
    if visit.suggestions:
        suggestions_title = Paragraph("التوصيات والمقترحات:", styles['Heading2'])
        elements.append(suggestions_title)
        suggestions_text = Paragraph(visit.suggestions, styles['BodyText'])
        elements.append(suggestions_text)
    
    # Signature
    elements.append(Spacer(1, 0.5*inch))
    signature_text = Paragraph(f"التوقيع: {visit.supervisor_signature}", styles['BodyText'])
    elements.append(signature_text)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Routes
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        identifier = request.form.get('username')
        password = request.form.get('password')
        user = User.find_user(identifier)
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('حساب المستخدم غير مفعل')
                return render_template('login.html')
                
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('اسم المستخدم/البريد الإلكتروني أو كلمة المرور غير صحيحة')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    total_visits = Visit.query.count()
    recent_visits = Visit.query.order_by(Visit.visit_date.desc()).limit(5).all()
    teachers_count = Teacher.query.count()
    supervisors_count = Supervisor.query.count()
    
    return render_template('dashboard.html', 
                         total_visits=total_visits,
                         recent_visits=recent_visits,
                         teachers_count=teachers_count,
                         supervisors_count=supervisors_count)

@app.route('/visit/new', methods=['GET', 'POST'])
@login_required
def new_visit():
    if request.method == 'POST':
        try:
            # Process form data
            teacher_id = request.form.get('teacher_id')
            teacher = Teacher.query.get(teacher_id)
            
            visit_data = {
                'visit_date': datetime.strptime(request.form.get('visit_date'), '%Y-%m-%d'),
                'school_name': request.form.get('school_name'),
                'teacher_id': teacher_id,
                'supervisor_id': request.form.get('supervisor_id'),
                'subject': request.form.get('subject'),
                'grade': request.form.get('grade'),
                'lesson_title': request.form.get('lesson_title'),
                'feedback_1': request.form.get('feedback_text_1'),
                'feedback_2': request.form.get('feedback_text_2'),
                'suggestions': request.form.get('suggestions'),
                'supervisor_signature': request.form.get('supervisor_signature'),
                'status': request.form.get('visit_status')
            }
            
            # Process follow-up date if provided
            follow_up = request.form.get('follow_up_date')
            if follow_up:
                visit_data['follow_up_date'] = datetime.strptime(follow_up, '%Y-%m-%d')
            
            # Collect evaluation scores
            management_scores = {}
            for i in range(1, 6):
                management_scores[f'management_{i}'] = request.form.get(f'management_{i}')
            
            teaching_scores = {}
            for i in range(1, 11):
                teaching_scores[f'teaching_{i}'] = request.form.get(f'teaching_{i}')
            
            feedback_scores = {}
            for i in range(1, 6):
                feedback_scores[f'feedback_{i}'] = request.form.get(f'feedback_{i}')
            
            visit_data['management_scores'] = json.dumps(management_scores)
            visit_data['teaching_scores'] = json.dumps(teaching_scores)
            visit_data['feedback_scores'] = json.dumps(feedback_scores)
            
            new_visit = Visit(**visit_data)
            db.session.add(new_visit)
            db.session.commit()
            
            # Send email if requested
            send_email = request.form.get('send_email')
            if send_email and teacher:
                supervisor = Supervisor.query.get(visit_data['supervisor_id'])
                send_visit_report_email(
                    teacher.email, 
                    teacher.name,
                    visit_data['visit_date'].strftime('%Y-%m-%d'),
                    supervisor.name if supervisor else 'مشرف',
                    new_visit.id
                )
                flash('تم إرسال التقرير إلى البريد الإلكتروني للمعلم')
            
            flash('تم حفظ بيانات الزيارة بنجاح')
            return redirect(url_for('visit_reports'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ أثناء حفظ البيانات: {str(e)}')
    
    teachers = Teacher.query.all()
    supervisors = Supervisor.query.all()
    return render_template('visit_form.html', 
                          teachers=teachers, 
                          supervisors=supervisors)

@app.route('/visits')
@login_required
def visit_reports():
    visits = Visit.query.order_by(Visit.visit_date.desc()).all()
    return render_template('visit_reports.html', visits=visits)

@app.route('/visit/<int:visit_id>')
@login_required
def visit_details(visit_id):
    visit = Visit.query.get_or_404(visit_id)
    
    # Parse JSON scores
    management_scores = json.loads(visit.management_scores) if visit.management_scores else {}
    teaching_scores = json.loads(visit.teaching_scores) if visit.teaching_scores else {}
    feedback_scores = json.loads(visit.feedback_scores) if visit.feedback_scores else {}
    
    return render_template('visit_details.html', 
                         visit=visit,
                         management_scores=management_scores,
                         teaching_scores=teaching_scores,
                         feedback_scores=feedback_scores)

@app.route('/visit/<int:visit_id>/send_email')
@login_required
def send_visit_email(visit_id):
    """إرسال التقرير بالبريد الإلكتروني"""
    visit = Visit.query.get_or_404(visit_id)
    
    try:
        success = send_visit_report_email(
            visit.teacher.email,
            visit.teacher.name,
            visit.visit_date.strftime('%Y-%m-%d'),
            visit.supervisor.name,
            visit.id
        )
        
        if success:
            flash('تم إرسال التقرير إلى البريد الإلكتروني للمعلم بنجاح')
        else:
            flash('حدث خطأ أثناء إرسال البريد الإلكتروني')
    except Exception as e:
        flash(f'حدث خطأ: {str(e)}')
    
    return redirect(url_for('visit_details', visit_id=visit_id))

@app.route('/visit/<int:visit_id>/pdf')
@login_required
def generate_pdf(visit_id):
    visit = Visit.query.get_or_404(visit_id)
    buffer = generate_pdf_buffer(visit)
    return send_file(buffer, as_attachment=True, download_name=f"تقرير_زيارة_{visit_id}.pdf", mimetype='application/pdf')

@app.route('/teachers')
@login_required
def teachers_list():
    teachers = Teacher.query.all()
    return render_template('teachers.html', teachers=teachers)

@app.route('/teacher/delete/<int:teacher_id>', methods=['POST'])
@login_required
@admin_required
def delete_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    
    # Check if teacher has visits
    if teacher.visits:
        flash('لا يمكن حذف المعلم لأنه لديه زيارات مسجلة')
        return redirect(url_for('teachers_list'))
    
    try:
        db.session.delete(teacher)
        db.session.commit()
        flash('تم حذف المعلم بنجاح')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء حذف المعلم: {str(e)}')
    
    return redirect(url_for('teachers_list'))

@app.route('/supervisors')
@login_required
def supervisors_list():
    supervisors = Supervisor.query.all()
    return render_template('supervisors.html', supervisors=supervisors)

@app.route('/supervisor/delete/<int:supervisor_id>', methods=['POST'])
@login_required
@admin_required
def delete_supervisor(supervisor_id):
    supervisor = Supervisor.query.get_or_404(supervisor_id)
    
    # Check if supervisor has visits
    if supervisor.visits:
        flash('لا يمكن حذف المشرف لأنه لديه زيارات مسجلة')
        return redirect(url_for('supervisors_list'))
    
    try:
        db.session.delete(supervisor)
        db.session.commit()
        flash('تم حذف المشرف بنجاح')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء حذف المشرف: {str(e)}')
    
    return redirect(url_for('supervisors_list'))

@app.route('/add_teacher', methods=['GET', 'POST'])
@login_required
@admin_required
def add_teacher():
    if request.method == 'POST':
        try:
            teacher_data = {
                'name': request.form.get('name'),
                'email': request.form.get('email'),
                'subject': request.form.get('subject'),
                'school': request.form.get('school'),
                'phone': request.form.get('phone'),
                'grade': request.form.get('grade')
            }
            
            new_teacher = Teacher(**teacher_data)
            db.session.add(new_teacher)
            db.session.commit()
            
            flash('تم إضافة المعلم بنجاح')
            return redirect(url_for('teachers_list'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ أثناء إضافة المعلم: {str(e)}')
    
    return render_template('add_teacher.html')

@app.route('/add_supervisor', methods=['GET', 'POST'])
@login_required
@admin_required
def add_supervisor():
    if request.method == 'POST':
        try:
            supervisor_data = {
                'name': request.form.get('name'),
                'email': request.form.get('email'),
                'specialty': request.form.get('specialty'),
                'phone': request.form.get('phone')
            }
            
            new_supervisor = Supervisor(**supervisor_data)
            db.session.add(new_supervisor)
            db.session.commit()
            
            flash('تم إضافة المشرف بنجاح')
            return redirect(url_for('supervisors_list'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ أثناء إضافة المشرف: {str(e)}')
    
    return render_template('add_supervisor.html')

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# Helper function to find available port
def find_available_port(start_port=5000, end_port=5010):
    """Find available port"""
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('localhost', port))
                return port
            except socket.error:
                continue
    return start_port

if __name__ == '__main__':
    with app.app_context():
        # Create database tables
        db.create_all()
        
        # Create default admin user if not exists
        if not User.query.filter_by(username='taanet@gmail.com').first():
            admin_user = User(
                username='taanet@gmail.com',
                email='taanet@gmail.com',
                name='مدير النظام',
                role='admin',
                is_active=True
            )
            admin_user.set_password('taha1975')
            db.session.add(admin_user)
            db.session.commit()
            
        # Add sample teachers if none exist
        if Teacher.query.count() == 0:
            teachers = [
                Teacher(name='أحمد محمد', email='ahmed@school.com', subject='الرياضيات', school='منارات المدينة المنورة', phone='0551234567', grade='الأول ابتدائي, الثاني ابتدائي'),
                Teacher(name='فاطمة عبدالله', email='fatima@school.com', subject='اللغة العربية', school='منارات المدينة المنورة', phone='0557654321', grade='الثالث ابتدائي, الرابع ابتدائي'),
                Teacher(name='خالد السعدي', email='khaled@school.com', subject='العلوم', school='منارات المدينة المنورة', phone='0551122334', grade='الخامس ابتدائي, السادس ابتدائي')
            ]
            for teacher in teachers:
                db.session.add(teacher)
            
        # Add sample supervisors if none exist
        if Supervisor.query.count() == 0:
            supervisors = [
                Supervisor(name='محمد علي', email='mohamed@edu.sa', specialty='الرياضيات', phone='0509876543'),
                Supervisor(name='سارة أحمد', email='sara@edu.sa', specialty='اللغة العربية', phone='0501234567'),
                Supervisor(name='عبدالله سالم', email='abdullah@edu.sa', specialty='العلوم', phone='0505556667')
            ]
            for supervisor in supervisors:
                db.session.add(supervisor)
            
        db.session.commit()
    
    # Find available port and run the application
    available_port = find_available_port()
    print(f"=" * 50)
    print(f"نظام إدارة الزيارات المدرسية")
    print(f"=" * 50)
    print(f"* التطبيق يعمل على:")
    print(f"* http://localhost:{available_port}")
    print(f"* http://127.0.0.1:{available_port}")
    print(f"=" * 50)
    print(f"بيانات الدخول:")
    print(f"* البريد الإلكتروني: taanet@gmail.com")
    print(f"* كلمة المرور: taha1975")
    print(f"=" * 50)
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=available_port, threaded=True)