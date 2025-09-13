from app import app
from models import db, User

with app.app_context():
    # حذف الجداول القديمة أولاً
    db.drop_all()
    
    # إنشاء جميع الجداول
    db.create_all()
    
    # إنشاء مستخدم افتراضي
    try:
        # تحقق أولاً إذا المستخدم موجود
        existing_user = User.query.filter_by(email='admin@school.com').first()
        if not existing_user:
            admin_user = User(
                email='admin@school.com',
                password='admin123',
                role='admin'
            )
            db.session.add(admin_user)
            db.session.commit()
            print("✅ تم إنشاء المستخدم الافتراضي: admin@school.com / admin123")
        else:
            print("⚠️  المستخدم موجود بالفعل")
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في إنشاء المستخدم: {e}")
    
    print("✅ تم تهيئة قاعدة البيانات بنجاح")