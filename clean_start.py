import os
import subprocess

# حذف قاعدة البيانات
if os.path.exists('school_visits.db'):
    os.remove('school_visits.db')
    print("تم حذف قاعدة البيانات")

# تشغيل التطبيق
subprocess.run(['python', 'app.py'])