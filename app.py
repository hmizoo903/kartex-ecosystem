import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# ---------------------------------------------------------
# DATABASE MODELS
# ---------------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), default='user')
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    
    wallet = db.relationship('Wallet', backref='owner', uselist=False, lazy=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    usd_balance = db.Column(db.Float, default=1000.0)  # Starting demo USD balance
    ktx_balance = db.Column(db.Float, default=400000.0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)  # 'BUY' or 'SELL'
    ktx_amount = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    total_value = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    price = db.Column(db.Float, nullable=False, default=0.10)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

# Helper Function
def get_current_price():
    latest = PriceHistory.query.order_by(PriceHistory.id.desc()).first()
    return latest.price if latest else 0.10

# ---------------------------------------------------------
# PUBLIC ROUTES
# ---------------------------------------------------------
@app.route('/')
def index():
    price = get_current_price()
    stats = {
        'total_supply': "1,000,000 KTX",
        'current_price': f"${price:.2f}",
        'simulated_market_cap': f"${(price * 1000000):,.2f}"
    }
    return render_template('index.html', stats=stats)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/tokenomics')
def tokenomics():
    return render_template('tokenomics.html')

@app.route('/roadmap')
def roadmap():
    return render_template('roadmap.html')

@app.route('/whitepaper')
def whitepaper():
    return render_template('whitepaper.html')

# ---------------------------------------------------------
# AUTH ROUTES
# ---------------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username').strip()
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash("Username or Email already exists.", "danger")
            return render_template('register.html')
            
        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, email=email, password_hash=pw_hash)
        db.session.add(new_user)
        db.session.commit()
        
        user_wallet = Wallet(user_id=new_user.id, usd_balance=1000.0, ktx_balance=400000.0)
        db.session.add(user_wallet)
        db.session.commit()
        
        flash("Account created! Please log in.", "success")
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        login_id = request.form.get('login_id').strip()
        password = request.form.get('password')
        
        user = User.query.filter((User.email == login_id.lower()) | (User.username == login_id)).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials.", "danger")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('index'))

# ---------------------------------------------------------
# DASHBOARD & WALLET SYSTEM (PHASE 3)
# ---------------------------------------------------------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please log in to access the dashboard.", "info")
        return redirect(url_for('login'))
        
    user = User.query.get(session['user_id'])
    current_price = get_current_price()
    portfolio_value = (user.wallet.ktx_balance * current_price) + user.wallet.usd_balance
    
    return render_template('dashboard.html', 
                           user=user, 
                           current_price=current_price, 
                           portfolio_value=portfolio_value)

@app.route('/wallet')
def wallet():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = User.query.get(session['user_id'])
    current_price = get_current_price()
    return render_template('wallet.html', user=user, current_price=current_price)

@app.route('/buy', methods=['POST'])
def buy_ktx():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = User.query.get(session['user_id'])
    current_price = get_current_price()
    
    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        amount = 0

    if amount <= 0:
        flash("Invalid amount.", "danger")
        return redirect(url_for('wallet'))

    total_cost = amount * current_price

    if user.wallet.usd_balance < total_cost:
        flash("Insufficient Demo USD Balance!", "danger")
        return redirect(url_for('wallet'))

    # Update Balances
    user.wallet.usd_balance -= total_cost
    user.wallet.ktx_balance += amount

    # Record Transaction
    tx = Transaction(user_id=user.id, transaction_type='BUY', ktx_amount=amount, price=current_price, total_value=total_cost)
    db.session.add(tx)
    db.session.commit()

    flash(f"Successfully bought {amount:,.2f} KTX for ${total_cost:,.2f} USD!", "success")
    return redirect(url_for('wallet'))

@app.route('/sell', methods=['POST'])
def sell_ktx():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = User.query.get(session['user_id'])
    current_price = get_current_price()
    
    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        amount = 0

    if amount <= 0:
        flash("Invalid amount.", "danger")
        return redirect(url_for('wallet'))

    if user.wallet.ktx_balance < amount:
        flash("Insufficient KTX Balance!", "danger")
        return redirect(url_for('wallet'))

    total_credit = amount * current_price

    # Update Balances
    user.wallet.ktx_balance -= amount
    user.wallet.usd_balance += total_credit

    # Record Transaction
    tx = Transaction(user_id=user.id, transaction_type='SELL', ktx_amount=amount, price=current_price, total_value=total_credit)
    db.session.add(tx)
    db.session.commit()

    flash(f"Successfully sold {amount:,.2f} KTX for ${total_credit:,.2f} USD!", "success")
    return redirect(url_for('wallet'))

@app.route('/transactions')
def transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = User.query.get(session['user_id'])
    user_txs = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.id.desc()).all()
    return render_template('transactions.html', transactions=user_txs)

@app.route('/api/price-history')
def price_history_api():
    history = PriceHistory.query.order_by(PriceHistory.id.asc()).all()
    data = [{
        'time': h.created_at.strftime('%H:%M:%S'),
        'price': h.price
    } for h in history]
    return jsonify(data)

# ---------------------------------------------------------
# ADMIN ROUTES (PHASE 4)
# ---------------------------------------------------------
@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('dashboard'))
        
    users = User.query.all()
    current_price = get_current_price()
    price_history = PriceHistory.query.order_by(PriceHistory.id.desc()).limit(10).all()
    
    return render_template('admin.html', users=users, current_price=current_price, price_history=price_history)

@app.route('/admin/update-price', methods=['POST'])
def update_price():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('dashboard'))
        
    try:
        new_price = float(request.form.get('price', 0))
    except ValueError:
        new_price = 0

    if new_price <= 0:
        flash("Invalid price value.", "danger")
        return redirect(url_for('admin_dashboard'))

    # Record new price point
    p = PriceHistory(price=new_price)
    db.session.add(p)
    db.session.commit()

    flash(f"KTX Token Price updated successfully to ${new_price:.2f}!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/adjust-balance', methods=['POST'])
def adjust_balance():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('dashboard'))
        
    user_id = request.form.get('user_id')
    try:
        usd_amount = float(request.form.get('usd_balance', 0))
        ktx_amount = float(request.form.get('ktx_balance', 0))
    except ValueError:
        flash("Invalid balance amounts.", "danger")
        return redirect(url_for('admin_dashboard'))

    target_user = User.query.get(user_id)
    if target_user and target_user.wallet:
        target_user.wallet.usd_balance = usd_amount
        target_user.wallet.ktx_balance = ktx_amount
        db.session.commit()
        flash(f"Balances updated for user {target_user.username}.", "success")
    else:
        flash("User or Wallet not found.", "danger")

    return redirect(url_for('admin_dashboard'))
# ---------------------------------------------------------
# INITIALIZATION
# ---------------------------------------------------------
def init_db():
    with app.app_context():
        db.create_all()
        if not PriceHistory.query.first():
            db.session.add(PriceHistory(price=0.10))
            db.session.add(PriceHistory(price=0.12))
            db.session.add(PriceHistory(price=0.11))
            db.session.add(PriceHistory(price=0.15))
            db.session.commit()

        admin_email = os.getenv('ADMIN_EMAIL')
        if admin_email and not User.query.filter_by(email=admin_email).first():
            hashed_pw = bcrypt.generate_password_hash(os.getenv('ADMIN_PASSWORD')).decode('utf-8')
            admin = User(
                username=os.getenv('ADMIN_USERNAME', 'admin'),
                email=admin_email,
                password_hash=hashed_pw,
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            
            admin_wallet = Wallet(user_id=admin.id, usd_balance=10000.0, ktx_balance=400000.0)
            db.session.add(admin_wallet)
            db.session.commit()
from functools import wraps

# ====================================================
# نظام لوحة التحكم والإدارة (Admin Panel)
# ====================================================

# 1. دالة حماية صفحات الأدمن (تمنع الزوار من الدخول بدون تسجيل)
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('غير مسموح لك بالوصول لصفحة الإدارة!', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# 2. صفحة تسجيل دخول الأدمن
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # بيانات الدخول السرية الخاصة بك (يمكنك تغييرها من هنا)
        ADMIN_USER = "admin"
        ADMIN_PASS = "Kartex2026Secret!"
        
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['is_admin'] = True
            session['user'] = username
            flash('تم تسجيل الدخول بنجاح كأدمن!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('بيانات الدخول غير صحيحة!', 'danger')
            
    return render_template('admin_login.html')

# 3. الصفحة الرئيسية للوحة الإدارة
@app.route('/admin')
@admin_required
def admin_dashboard():
    # جلب جميع المستخدمين المسجلين في الموقع
    users = User.query.all()
    total_users = len(users)
    return render_template('admin_dashboard.html', users=users, total_users=total_users)

# 4. أمر حذف مستخدم من قاعدة البيانات
@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f'تم حذف المستخدم {user.username} بنجاح.', 'success')
    return redirect(url_for('admin_dashboard'))

# 5. تسجيل الخروج من الإدارة
@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    flash('تم تسجيل الخروج من لوحة الإدارة.', 'info')
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)