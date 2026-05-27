from main import app, db
from database import User, Message
from werkzeug.security import generate_password_hash
import sqlalchemy as sa

with app.app_context():
    db.create_all()
    
    # Create admin
    if not db.session.execute(sa.select(User).where(User.username == 'admin')).first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            email='admin@example.com',
            role='admin'
        )
        db.session.add(admin)
    
    # Create sample user
    if not db.session.execute(sa.select(User).where(User.username == 'john')).first():
        john = User(
            username='john',
            password=generate_password_hash('user123'),
            email='john@example.com',
            role='user'
        )
        db.session.add(john)
    
    db.session.commit()
    print("Database initialized!")