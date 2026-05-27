from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import db, User, Message
import sqlalchemy as sa
#from main import app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///messages.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Create database tables
with app.app_context():
    db.create_all()
    
    # Create default admin if not exists
    admin_exists = db.session.execute(sa.select(User).where(User.username == 'admin')).first()
    if not admin_exists:
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            email='admin@example.com',
            role='admin'
        )
        db.session.add(admin)
        
        # Create sample users
        john = User(
            username='john',
            password=generate_password_hash('user123'),
            email='john@example.com',
            role='user'
        )
        jane = User(
            username='jane',
            password=generate_password_hash('user123'),
            email='jane@example.com',
            role='user'
        )
        db.session.add_all([john, jane])
        db.session.commit()
        print("Database initialized with default users!")

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        stmt = sa.select(User).where(User.username == username)
        user = db.session.execute(stmt).scalar_one_or_none()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'Welcome back, {username}!', 'success')
            
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password!', 'danger')
    
    return render_template('login.html')

@app.route('/manage_users', methods=['GET', 'POST'])
def manage_users():
    if current_user.is_authenticated and current_user.role != 'admin':
        return redirect(url_for('index'))
    if current_user.is_authenticated and current_user.role == 'admin':
        stmt = sa.select(User).order_by(User.created_at.desc())
        all_users = db.session.execute(stmt).scalars().all()
        return render_template('manage_users.html', users=all_users)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated and current_user.role != 'admin':
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        stmt = sa.select(User).where(User.username == username)
        existing_user = db.session.execute(stmt).scalar_one_or_none()
        
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
        elif len(password) < 6:
            flash('Password must be at least 6 characters!', 'danger')
        elif existing_user:
            flash('Username already exists!', 'danger')
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(
                username=username,
                password=hashed_password,
                email=email,
                role='user'
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/admin/dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied. Admin only!', 'danger')
        return redirect(url_for('user_dashboard'))
    
    stmt = sa.select(User).order_by(User.created_at.desc())
    all_users = db.session.execute(stmt).scalars().all()
    users = [u for u in all_users if u.role == 'user']
    
    if request.method == 'POST' and 'send_to_user' in request.form:
        receiver_id = request.form.get('receiver_id')
        subject = request.form.get('subject')
        message_text = request.form.get('message')
        
        if receiver_id and subject and message_text:
            message = Message(
                sender_id=current_user.id,
                receiver_id=receiver_id,
                subject=subject,
                message=message_text
            )
            db.session.add(message)
            db.session.commit()
            flash('Message sent to user successfully!', 'success')
        else:
            flash('Please fill all fields!', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST' and 'reply_to_user' in request.form:
        reply_message = request.form.get('reply_message')
        user_id = request.form.get('user_id')
        
        if reply_message and user_id:
            message = Message(
                sender_id=current_user.id,
                receiver_id=user_id,
                subject="Re: Your message",
                message=reply_message
            )
            db.session.add(message)
            db.session.commit()
            flash('Reply sent to user!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    stmt = sa.select(Message).where(
        Message.receiver_id == current_user.id,
        Message.sender.has(role='user')
    ).order_by(Message.created_at.desc())
    received_messages = db.session.execute(stmt).scalars().all()
    
    stmt = sa.select(Message).where(
        Message.sender_id == current_user.id,
        Message.receiver.has(role='user')
    ).order_by(Message.created_at.desc())
    sent_messages = db.session.execute(stmt).scalars().all()
    
    return render_template('admin_dashboard.html', 
                         users=users,
                         all_users=all_users,
                         sent_messages=sent_messages,
                         received_messages=received_messages)

@app.route('/user/dashboard', methods=['GET', 'POST'])
@login_required
def user_dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        subject = request.form.get('subject')
        message_text = request.form.get('message')
        
        stmt = sa.select(User).where(User.role == 'admin')
        admin = db.session.execute(stmt).scalar_one_or_none()
        
        if admin and subject and message_text:
            message = Message(
                sender_id=current_user.id,
                receiver_id=admin.id,
                subject=subject,
                message=message_text
            )
            db.session.add(message)
            db.session.commit()
            flash('Message sent to Admin successfully!', 'success')
        else:
            flash('Please fill all fields!', 'danger')
        return redirect(url_for('user_dashboard'))
    
    stmt = sa.select(Message).where(
        Message.receiver_id == current_user.id,
        Message.sender.has(role='admin')
    ).order_by(Message.created_at.desc())
    received_messages = db.session.execute(stmt).scalars().all()
    
    stmt = sa.select(Message).where(
        Message.sender_id == current_user.id,
        Message.receiver.has(role='admin')
    ).order_by(Message.created_at.desc())
    sent_messages = db.session.execute(stmt).scalars().all()
    
    unread_count = len([m for m in received_messages if not m.is_read])
    
    return render_template('user_dashboard.html', 
                         received_messages=received_messages,
                         sent_messages=sent_messages,
                         unread_count=unread_count)

@app.route('/user/mark_read/<int:message_id>')
@login_required
def mark_read(message_id):
    message = db.session.get(Message, message_id)
    
    if not message:
        flash('Message not found!', 'danger')
        return redirect(url_for('user_dashboard'))
    
    if message.receiver_id != current_user.id:
        flash('Access denied!', 'danger')
        return redirect(url_for('user_dashboard'))
    
    message.is_read = True
    db.session.commit()
    flash('Message marked as read.', 'success')
    return redirect(url_for('user_dashboard'))

@app.route('/admin/delete_user', methods=['POST'])
@login_required
def admin_delete_user():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('user_dashboard'))
    
    user_id = request.form.get('user_id')
    user_to_delete = db.session.get(User, user_id)
    
    if user_to_delete.id == current_user.id:
        flash('You cannot delete your own account!', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    try:
        stmt = sa.delete(Message).where(
            (Message.sender_id == user_id) | (Message.receiver_id == user_id)
        )
        db.session.execute(stmt)
        db.session.delete(user_to_delete)
        db.session.commit()
        flash(f'User "{user_to_delete.username}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'danger')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_user', methods=['POST'])
@login_required
def admin_edit_user():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('user_dashboard'))
    
    user_id = request.form.get('user_id')
    username = request.form.get('username')
    email = request.form.get('email')
    role = request.form.get('role')
    new_password = request.form.get('password')
    
    user = db.session.get(User, user_id)
    
    if not user:
        flash('User not found!', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    user.username = username
    user.email = email
    user.role = role
    
    if new_password and len(new_password) >= 6:
        user.password = generate_password_hash(new_password)
        flash(f'User updated successfully! New password: {new_password}', 'success')
    else:
        flash('User updated successfully!', 'success')
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating user: {str(e)}', 'danger')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/conversation/<int:user_id>')
@login_required
def admin_conversation(user_id):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('user_dashboard'))
    
    other_user = db.session.get(User, user_id)
    if not other_user:
        flash('User not found!', 'danger')
        return redirect(url_for('manage_users'))
    
    stmt = sa.select(Message).where(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc())
    
    messages = db.session.execute(stmt).scalars().all()
    
    for msg in messages:
        if msg.sender_id == user_id and msg.receiver_id == current_user.id and not msg.is_read:
            msg.is_read = True
    db.session.commit()
    
    return render_template('admin_conversation.html', 
                         other_user=other_user, 
                         messages=messages)

@app.route('/admin/send_message/<int:user_id>', methods=['POST'])
@login_required
def admin_send_message(user_id):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('user_dashboard'))
    
    message_text = request.form.get('message')
    
    if message_text:
        message = Message(
            sender_id=current_user.id,
            receiver_id=user_id,
            subject="Message from Admin",
            message=message_text
        )
        db.session.add(message)
        db.session.commit()
        flash('Message sent!', 'success')
    
    return redirect(url_for('admin_conversation', user_id=user_id))

@app.route('/user/conversation/<int:admin_id>')
@login_required
def user_conversation(admin_id):
    if current_user.role != 'user':
        flash('Access denied!', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    admin = db.session.get(User, admin_id)
    if not admin or admin.role != 'admin':
        flash('Admin not found!', 'danger')
        return redirect(url_for('user_dashboard'))
    
    stmt = sa.select(Message).where(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == admin_id)) |
        ((Message.sender_id == admin_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc())
    
    messages = db.session.execute(stmt).scalars().all()
    
    for msg in messages:
        if msg.sender_id == admin_id and msg.receiver_id == current_user.id and not msg.is_read:
            msg.is_read = True
    db.session.commit()
    
    return render_template('user_conversation.html', admin=admin, messages=messages)

@app.route('/user/send_message/<int:admin_id>', methods=['POST'])
@login_required
def user_send_message(admin_id):
    if current_user.role != 'user':
        flash('Access denied!', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    message_text = request.form.get('message')
    
    if message_text:
        message = Message(
            sender_id=current_user.id,
            receiver_id=admin_id,
            subject="Message from User",
            message=message_text
        )
        db.session.add(message)
        db.session.commit()
        flash('Message sent!', 'success')
    
    return redirect(url_for('user_conversation', admin_id=admin_id))
# Get all users for user to chat with (excluding current user)
@app.route('/user/contacts')
@login_required
def user_contacts():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    # Get all other users (both admin and regular users)
    stmt = sa.select(User).where(User.id != current_user.id).order_by(User.username)
    contacts = db.session.execute(stmt).scalars().all()
    
    # Get last message for each contact to show preview
    contacts_with_preview = []
    for contact in contacts:
        # Get last message between current user and this contact
        stmt = sa.select(Message).where(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == contact.id)) |
            ((Message.sender_id == contact.id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.created_at.desc()).limit(1)
        
        last_message = db.session.execute(stmt).scalar_one_or_none()
        
        # Count unread messages from this contact
        unread_stmt = sa.select(Message).where(
            Message.sender_id == contact.id,
            Message.receiver_id == current_user.id,
            Message.is_read == False
        )
        unread_count = len(db.session.execute(unread_stmt).scalars().all())
        
        contacts_with_preview.append({
            'user': contact,
            'last_message': last_message,
            'unread_count': unread_count
        })
    
    return render_template('user_contacts.html', contacts=contacts_with_preview)

# Chat view for user-to-user
@app.route('/user/chat/<int:user_id>')
@login_required
def user_chat(user_id):
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    # Get the other user
    other_user = db.session.get(User, user_id)
    if not other_user:
        flash('User not found!', 'danger')
        return redirect(url_for('user_contacts'))
    
    # Get all messages between current user and other user
    stmt = sa.select(Message).where(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc())
    
    messages = db.session.execute(stmt).scalars().all()
    
    # Mark messages from other user as read
    for msg in messages:
        if msg.sender_id == user_id and msg.receiver_id == current_user.id and not msg.is_read:
            msg.is_read = True
    db.session.commit()
    
    return render_template('user_chat.html', other_user=other_user, messages=messages)

# Send message to another user
@app.route('/user/send_chat/<int:user_id>', methods=['POST'])
@login_required
def user_send_chat(user_id):
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    message_text = request.form.get('message')
    
    if message_text:
        message = Message(
            sender_id=current_user.id,
            receiver_id=user_id,
            subject="Direct Message",
            message=message_text
        )
        db.session.add(message)
        db.session.commit()
        flash('Message sent!', 'success')
    else:
        flash('Message cannot be empty!', 'danger')
    
    return redirect(url_for('user_chat', user_id=user_id))
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)