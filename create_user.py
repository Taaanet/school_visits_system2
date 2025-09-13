from app import app
from models import db, User

with app.app_context():
    # تحقق إذا المستخدم موجود
    user = User.query.filter_by(email='admin@school.com').first()
    if user:
        print(f"✅ المستخدم موجود: {user.email}")
    else:
        # أنشئ مستخدم جديد
        new_user = User(
            email='admin@school.com',
            password='admin123',
            role='admin'
        )
        db.session.add(new_user)
        db.session.commit()
        print("✅ تم إنشاء المستخدم: admin@school.com / admin123")