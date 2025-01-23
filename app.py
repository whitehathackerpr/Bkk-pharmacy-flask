from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import MySQLdb.cursors
from datetime import datetime, date
import locale
from decimal import Decimal
from dateutil.relativedelta import relativedelta
import pandas as pd
from fpdf import FPDF
from io import BytesIO


app = Flask(__name__)

# Database configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '752002'
app.config['MYSQL_DB'] = 'bkk_pharmacy'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
app.secret_key = 'your_secret_key_here'

mysql = MySQL(app)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Please login first!', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
@app.route('/home')
@login_required
def home():
    try:
        cursor = mysql.connection.cursor(dictionary=True)
        
        # Get total medications
        cursor.execute("""
            SELECT COUNT(*) as total,
                   COALESCE(SUM(CASE WHEN quantity <= reorder_level THEN 1 ELSE 0 END), 0) as low_stock
            FROM inventory
            WHERE active = TRUE
        """)
        inventory_data = cursor.fetchone()
        total_medications = inventory_data['total']
        low_stock_count = inventory_data['low_stock']
        
        # Get active prescriptions for current month
        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM prescriptions 
            WHERE status = 'active' 
            AND MONTH(created_at) = MONTH(CURRENT_DATE())
            AND YEAR(created_at) = YEAR(CURRENT_DATE())
        """)
        prescription_data = cursor.fetchone()
        monthly_prescriptions = prescription_data['total']
        
        # Get monthly sales
        cursor.execute("""
            SELECT 
                COALESCE(SUM(total_amount), 0) as monthly_amount,
                COUNT(*) as monthly_count
            FROM sales 
            WHERE MONTH(created_at) = MONTH(CURRENT_DATE())
            AND YEAR(created_at) = YEAR(CURRENT_DATE())
        """)
        sales_data = cursor.fetchone()
        monthly_amount = Decimal(sales_data['monthly_amount'])
        monthly_sales = f"UGX {monthly_amount:,.0f}"
        monthly_transactions = sales_data['monthly_count']
        
        # Get pending deliveries
        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM sales 
            WHERE delivery_status = 'pending'
            AND created_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
        """)
        delivery_data = cursor.fetchone()
        pending_deliveries = delivery_data['total']
        
        # Get current month name
        current_month = datetime.now().strftime('%B %Y')
        
        # Get low stock items with monthly sales trend
        cursor.execute("""
            SELECT 
                i.id,
                i.name, 
                i.quantity,
                i.reorder_level,
                COALESCE(
                    (SELECT SUM(si.quantity)
                     FROM sales_items si
                     WHERE si.item_id = i.id
                     AND MONTH(si.created_at) = MONTH(CURRENT_DATE())
                     AND YEAR(si.created_at) = YEAR(CURRENT_DATE())
                    ), 0
                ) as monthly_sales
            FROM inventory i
            WHERE i.quantity <= i.reorder_level
                AND i.active = TRUE
            ORDER BY i.quantity ASC
            LIMIT 5
        """)
        low_stock_items = cursor.fetchall()
        
        # Get recent activities (last 30 days)
        cursor.execute("""
            (SELECT 
                'sale' as type,
                CONCAT('New sale: UGX ', FORMAT(total_amount, 0)) as description,
                created_at,
                total_amount as amount
            FROM sales
            WHERE created_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
            UNION ALL
            (SELECT 
                'prescription' as type,
                CONCAT('Prescription for ', patient_name) as description,
                created_at,
                0 as amount
            FROM prescriptions
            WHERE created_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
            ORDER BY created_at DESC
            LIMIT 5
        """)
        recent_activities = cursor.fetchall()
        
        cursor.close()
        
        return render_template('home.html',
                             total_medications=total_medications,
                             monthly_prescriptions=monthly_prescriptions,
                             monthly_sales=monthly_sales,
                             monthly_transactions=monthly_transactions,
                             pending_deliveries=pending_deliveries,
                             low_stock_items=low_stock_items,
                             low_stock_count=low_stock_count,
                             recent_activities=recent_activities,
                             current_month=current_month)
                             
    except Exception as e:
        print(f"Error loading home page: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return render_template('home.html',
                             total_medications=0,
                             monthly_prescriptions=0,
                             monthly_sales="UGX 0",
                             monthly_transactions=0,
                             pending_deliveries=0,
                             low_stock_items=[],
                             low_stock_count=0,
                             recent_activities=[],
                             current_month=datetime.now().strftime('%B %Y'))

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        cursor = mysql.connection.cursor()
        
        # Get today's stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_sales,
                COALESCE(SUM(total_price), 0) as total_revenue,
                COALESCE(SUM(quantity), 0) as total_items
            FROM sales 
            WHERE DATE(created_at) = CURDATE()
        """)
        today_stats = cursor.fetchone()
        
        # Get total medications
        cursor.execute("SELECT COUNT(*) as count FROM medications")
        total_medications = cursor.fetchone()
        
        # Get pending prescriptions
        cursor.execute("SELECT COUNT(*) as count FROM prescriptions WHERE status = 'pending'")
        pending_prescriptions = cursor.fetchone()
        
        # Get low stock items
        cursor.execute("""
            SELECT name, stock, min_stock 
            FROM medications 
            WHERE stock <= min_stock 
            ORDER BY stock ASC 
            LIMIT 5
        """)
        low_stock_items = cursor.fetchall()
        
        # Get recent sales
        cursor.execute("""
            SELECT s.*, m.name as medication_name 
            FROM sales s 
            JOIN medications m ON s.medication_id = m.id 
            ORDER BY s.created_at DESC 
            LIMIT 5
        """)
        recent_sales = cursor.fetchall()
        
        cursor.close()
        
        return render_template('dashboard.html',
                             today_stats=today_stats,
                             total_medications=total_medications['count'],
                             pending_prescriptions=pending_prescriptions['count'],
                             low_stock_items=low_stock_items,
                             recent_sales=recent_sales)
                             
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        flash('Error loading dashboard', 'danger')
        return render_template('dashboard.html',
                             today_stats={'total_sales': 0, 'total_revenue': 0, 'total_items': 0},
                             total_medications=0,
                             pending_prescriptions=0,
                             low_stock_items=[],
                             recent_sales=[])

@app.route('/list_inventory')
@login_required
def list_inventory():
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT * FROM medications 
            ORDER BY name ASC
        """)
        medications = cursor.fetchall()
        cursor.close()
        
        return render_template('inventory/list.html', medications=medications)
        
    except Exception as e:
        print(f"Error fetching inventory: {str(e)}")
        flash('Error loading inventory. Please try again.', 'danger')
        return render_template('inventory/list.html', medications=[])

@app.route('/list_prescriptions')
@login_required
def list_prescriptions():
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT p.*, m.name as medication_name 
            FROM prescriptions p 
            JOIN medications m ON p.medication_id = m.id 
            ORDER BY p.created_at DESC
        """)
        prescriptions = cursor.fetchall()
        cursor.close()
        
        return render_template('prescriptions/list.html', prescriptions=prescriptions)
        
    except Exception as e:
        print(f"Error fetching prescriptions: {str(e)}")
        flash('Error loading prescriptions. Please try again.', 'danger')
        return render_template('prescriptions/list.html', prescriptions=[])

@app.route('/list_sales')
@login_required
def list_sales():
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT s.*, m.name as medication_name 
            FROM sales s 
            JOIN medications m ON s.medication_id = m.id 
            ORDER BY s.created_at DESC
        """)
        sales = cursor.fetchall()
        cursor.close()
        
        return render_template('sales/list.html', sales=sales)
        
    except Exception as e:
        print(f"Error fetching sales: {str(e)}")
        flash('Error loading sales. Please try again.', 'danger')
        return render_template('sales/list.html', sales=[])

@app.route('/report')
@login_required
def report():
    try:
        cursor = mysql.connection.cursor()
        
        # Get sales summary
        cursor.execute("""
            SELECT 
                DATE(created_at) as sale_date,
                COUNT(*) as total_sales,
                SUM(total_price) as total_revenue,
                SUM(discount) as total_discounts
            FROM sales
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(created_at)
            ORDER BY sale_date DESC
        """)
        sales_summary = cursor.fetchall()
        
        # Get low stock medications
        cursor.execute("""
            SELECT name, stock, min_stock
            FROM medications
            WHERE stock <= min_stock
            ORDER BY stock ASC
        """)
        low_stock = cursor.fetchall()
        
        # Get top selling medications
        cursor.execute("""
            SELECT 
                m.name,
                SUM(s.quantity) as total_quantity,
                SUM(s.total_price) as total_revenue
            FROM sales s
            JOIN medications m ON s.medication_id = m.id
            GROUP BY m.id, m.name
            ORDER BY total_quantity DESC
            LIMIT 5
        """)
        top_selling = cursor.fetchall()
        
        # Get prescription status summary
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM prescriptions
            GROUP BY status
        """)
        prescription_summary = cursor.fetchall()
        
        cursor.close()
        
        return render_template('reports/index.html',
                             sales_summary=sales_summary,
                             low_stock=low_stock,
                             top_selling=top_selling,
                             prescription_summary=prescription_summary)
                             
    except Exception as e:
        print(f"Error generating report: {str(e)}")
        flash('Error generating report. Please try again.', 'danger')
        return render_template('reports/index.html')

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/users')
@login_required
def list_users():
    if session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
        
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Fetch users
        cursor.execute("""
            SELECT 
                id,
                username,
                email,
                role,
                IFNULL(active, TRUE) as active,
                DATE_FORMAT(created_at, '%Y-%m-%d') as created_at
            FROM users 
            ORDER BY created_at DESC
        """)
        
        users = cursor.fetchall()
        cursor.close()
                
        return render_template('users/list.html', users=users)
        
    except Exception as e:
        print(f"Error fetching users: {str(e)}")
        flash('Error loading users: ' + str(e), 'danger')
        return render_template('users/list.html', users=[])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        cursor.close()
        
        if user and check_password_hash(user['password'], password):
            session['loggedin'] = True
            session['id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password!', 'danger')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            # Get form data
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            role = request.form['role']  # Make sure this matches your form's select name
            
            # Hash the password
            hashed_password = generate_password_hash(password)
            
            # Create database cursor
            cursor = mysql.connection.cursor()
            
            # Check if username already exists
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            if cursor.fetchone():
                flash('Username already exists!', 'danger')
                return render_template('signup.html')
            
            # Check if email already exists
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            if cursor.fetchone():
                flash('Email already exists!', 'danger')
                return render_template('signup.html')
            
            # Insert new user with role
            cursor.execute('''
                INSERT INTO users (username, email, password, role) 
                VALUES (%s, %s, %s, %s)
            ''', (username, email, hashed_password, role))
            
            # Commit the transaction
            mysql.connection.commit()
            cursor.close()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            print(f"Registration error: {str(e)}")
            flash('Registration failed! Please try again.', 'danger')
            return render_template('signup.html')
            
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/forgot_password')
def forgot_password():
    return render_template('forgot_password.html')

# Medication routes
@app.route('/medications/new', methods=['GET', 'POST'])
@login_required
def new_medication():
    if request.method == 'POST':
        try:
            name = request.form['name']
            generic_name = request.form['generic_name']
            category = request.form['category']
            description = request.form['description']
            price = request.form['price']
            stock = request.form['stock']
            min_stock = request.form['min_stock']
            manufacturer = request.form['manufacturer']
            expiry_date = request.form['expiry_date']
            
            cursor = mysql.connection.cursor()
            cursor.execute("""
                INSERT INTO medications (
                    name, generic_name, category, description, 
                    price, stock, min_stock, manufacturer, expiry_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                name, generic_name, category, description,
                price, stock, min_stock, manufacturer, expiry_date
            ))
            mysql.connection.commit()
            cursor.close()
            
            flash('Medication added successfully!', 'success')
            return redirect(url_for('list_inventory'))
            
        except Exception as e:
            print(f"Error adding medication: {str(e)}")
            flash('Error adding medication. Please try again.', 'danger')
    
    return render_template('medications/new.html')

@app.route('/medications/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_medication(id):
    cursor = mysql.connection.cursor()
    
    if request.method == 'POST':
        try:
            name = request.form['name']
            generic_name = request.form['generic_name']
            category = request.form['category']
            description = request.form['description']
            price = request.form['price']
            stock = request.form['stock']
            min_stock = request.form['min_stock']
            manufacturer = request.form['manufacturer']
            expiry_date = request.form['expiry_date']
            
            cursor.execute("""
                UPDATE medications SET 
                    name=%s, generic_name=%s, category=%s, description=%s,
                    price=%s, stock=%s, min_stock=%s, manufacturer=%s, expiry_date=%s
                WHERE id=%s
            """, (
                name, generic_name, category, description,
                price, stock, min_stock, manufacturer, expiry_date, id
            ))
            mysql.connection.commit()
            
            flash('Medication updated successfully!', 'success')
            return redirect(url_for('list_inventory'))
            
        except Exception as e:
            print(f"Error updating medication: {str(e)}")
            flash('Error updating medication. Please try again.', 'danger')
    
    # Get medication data for editing
    cursor.execute("SELECT * FROM medications WHERE id = %s", (id,))
    medication = cursor.fetchone()
    cursor.close()
    
    if medication is None:
        flash('Medication not found!', 'danger')
        return redirect(url_for('list_inventory'))
        
    return render_template('medications/edit.html', medication=medication)

@app.route('/medications/delete/<int:id>')
@login_required
def delete_medication(id):
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("DELETE FROM medications WHERE id = %s", (id,))
        mysql.connection.commit()
        cursor.close()
        
        flash('Medication deleted successfully!', 'success')
    except Exception as e:
        print(f"Error deleting medication: {str(e)}")
        flash('Error deleting medication. Please try again.', 'danger')
        
    return redirect(url_for('list_inventory'))

# Prescription routes
@app.route('/prescriptions/new', methods=['GET', 'POST'])
@login_required
def new_prescription():
    if request.method == 'POST':
        try:
            patient_name = request.form['patient_name']
            patient_age = request.form['patient_age']
            patient_contact = request.form['patient_contact']
            medication_id = request.form['medication_id']
            quantity = request.form['quantity']
            dosage = request.form['dosage']
            doctor_name = request.form['doctor_name']
            notes = request.form.get('notes', '')
            
            cursor = mysql.connection.cursor()
            cursor.execute("""
                INSERT INTO prescriptions (
                    patient_name, patient_age, patient_contact, medication_id,
                    quantity, dosage, doctor_name, notes, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            """, (
                patient_name, patient_age, patient_contact, medication_id,
                quantity, dosage, doctor_name, notes
            ))
            mysql.connection.commit()
            cursor.close()
            
            flash('Prescription added successfully!', 'success')
            return redirect(url_for('list_prescriptions'))
            
        except Exception as e:
            print(f"Error adding prescription: {str(e)}")
            flash('Error adding prescription. Please try again.', 'danger')
    
    # Get medications list for dropdown
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, name FROM medications ORDER BY name")
    medications = cursor.fetchall()
    cursor.close()
    
    return render_template('prescriptions/new.html', medications=medications)

# Sales routes
@app.route('/sales/new', methods=['GET', 'POST'])
@login_required
def new_sale():
    if request.method == 'POST':
        try:
            prescription_id = request.form.get('prescription_id')
            medication_id = request.form['medication_id']
            quantity = int(request.form['quantity'])
            unit_price = float(request.form['unit_price'])
            discount = float(request.form.get('discount', 0))
            payment_method = request.form['payment_method']
            customer_name = request.form['customer_name']
            customer_contact = request.form['customer_contact']
            notes = request.form.get('notes', '')
            
            total_price = (quantity * unit_price) - discount
            
            cursor = mysql.connection.cursor()
            
            # Insert sale record
            cursor.execute("""
                INSERT INTO sales (
                    prescription_id, medication_id, quantity, unit_price,
                    total_price, discount, payment_method, customer_name,
                    customer_contact, notes, delivery_status, paid
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', FALSE)
            """, (
                prescription_id, medication_id, quantity, unit_price,
                total_price, discount, payment_method, customer_name,
                customer_contact, notes
            ))
            
            # Update medication stock
            cursor.execute("""
                UPDATE medications 
                SET stock = stock - %s 
                WHERE id = %s
            """, (quantity, medication_id))
            
            mysql.connection.commit()
            cursor.close()
            
            flash('Sale recorded successfully!', 'success')
            return redirect(url_for('list_sales'))
            
        except Exception as e:
            print(f"Error recording sale: {str(e)}")
            flash('Error recording sale. Please try again.', 'danger')
    
    # Get medications and prescriptions for dropdowns
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, name, price, stock FROM medications WHERE stock > 0 ORDER BY name")
    medications = cursor.fetchall()
    
    cursor.execute("""
        SELECT p.id, p.patient_name, m.name as medication_name 
        FROM prescriptions p 
        JOIN medications m ON p.medication_id = m.id 
        WHERE p.status = 'pending'
    """)
    prescriptions = cursor.fetchall()
    cursor.close()
    
    return render_template('sales/new.html', 
                         medications=medications,
                         prescriptions=prescriptions)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        try:
            # Get form data
            notification_preferences = request.form.getlist('notifications')
            theme = request.form.get('theme')
            language = request.form.get('language')
            timezone = request.form.get('timezone')
            
            # Update user settings in database
            cursor = mysql.connection.cursor()
            cursor.execute("""
                UPDATE user_settings 
                SET 
                    notifications = %s,
                    theme = %s,
                    language = %s,
                    timezone = %s
                WHERE user_id = %s
            """, (
                ','.join(notification_preferences),
                theme,
                language,
                timezone,
                session['id']
            ))
            mysql.connection.commit()
            cursor.close()
            
            flash('Settings updated successfully!', 'success')
            
        except Exception as e:
            print(f"Settings update error: {str(e)}")
            flash('Error updating settings. Please try again.', 'danger')
            
    # Get current settings
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT * FROM user_settings 
            WHERE user_id = %s
        """, (session['id'],))
        settings = cursor.fetchone()
        cursor.close()
        
        if not settings:
            # Create default settings if none exist
            cursor = mysql.connection.cursor()
            cursor.execute("""
                INSERT INTO user_settings (user_id, notifications, theme, language, timezone)
                VALUES (%s, 'low_stock,sales', 'light', 'en', 'UTC')
            """, (session['id'],))
            mysql.connection.commit()
            cursor.close()
            
            settings = {
                'notifications': 'low_stock,sales',
                'theme': 'light',
                'language': 'en',
                'timezone': 'UTC'
            }
            
    except Exception as e:
        print(f"Settings fetch error: {str(e)}")
        settings = {
            'notifications': 'low_stock,sales',
            'theme': 'light',
            'language': 'en',
            'timezone': 'UTC'
        }
    
    return render_template('settings.html', settings=settings)

@app.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Access denied'}), 403
        
    if int(session.get('user_id')) == user_id:
        return jsonify({'error': 'Cannot modify own status'}), 400
        
    try:
        cursor = mysql.connection.cursor()
        
        # Get current status
        cursor.execute('SELECT active FROM users WHERE id = %s', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        # Toggle status
        new_status = not user['active']
        cursor.execute('UPDATE users SET active = %s WHERE id = %s', (new_status, user_id))
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({'success': True, 'new_status': new_status})
        
    except Exception as e:
        print(f"Error toggling user status: {str(e)}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/users/new', methods=['GET', 'POST'])
@login_required
def new_user():
    if session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        try:
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            role = request.form['role']
            
            # Hash the password
            hashed_password = generate_password_hash(password)
            
            cursor = mysql.connection.cursor()
            
            # Check if username exists
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            if cursor.fetchone():
                flash('Username already exists!', 'danger')
                return render_template('users/new.html')
            
            # Check if email exists
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            if cursor.fetchone():
                flash('Email already exists!', 'danger')
                return render_template('users/new.html')
            
            # Create new user
            cursor.execute('''
                INSERT INTO users (username, email, password, role, active) 
                VALUES (%s, %s, %s, %s, TRUE)
            ''', (username, email, hashed_password, role))
            
            mysql.connection.commit()
            cursor.close()
            
            flash('User created successfully!', 'success')
            return redirect(url_for('list_users'))
            
        except Exception as e:
            print(f"Error creating user: {str(e)}")
            flash('Error creating user. Please try again.', 'danger')
            
    return render_template('users/new.html')

@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
        
    try:
        cursor = mysql.connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user = cursor.fetchone()
        cursor.close()
        
        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('list_users'))
            
        if request.method == 'POST':
            # Handle user update logic here
            pass
            
        return render_template('users/edit.html', user=user)
        
    except Exception as e:
        print(f"Error editing user: {str(e)}")
        flash('Error editing user', 'danger')
        return redirect(url_for('list_users'))

@app.route('/sales/<int:sale_id>/update', methods=['POST'])
@login_required
def update_sale(sale_id):
    try:
        cursor = mysql.connection.cursor(dictionary=True)
        
        # Get form data
        payment_method = request.form.get('payment_method')
        payment_status = request.form.get('payment_status')
        delivery_status = request.form.get('delivery_status')
        notes = request.form.get('notes')
        
        # Update sale in database
        cursor.execute("""
            UPDATE sales 
            SET payment_method = %s,
                paid = %s,
                delivery_status = %s,
                notes = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (payment_method, payment_status == 'paid', delivery_status, notes, sale_id))
        
        mysql.connection.commit()
        cursor.close()
        
        # Log the activity
        log_activity(f'Updated sale #{sale_id}', 'sale_update')
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error updating sale: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/sales/<int:sale_id>/details')
@login_required
def get_sale_details(sale_id):
    try:
        cursor = mysql.connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.*, c.name as customer_name 
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.id = %s
        """, (sale_id,))
        sale = cursor.fetchone()
        cursor.close()
        
        if sale:
            return jsonify({'success': True, 'sale': sale})
        return jsonify({'success': False, 'message': 'Sale not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/sales/<int:sale_id>/mark-paid', methods=['POST'])
@login_required
def mark_sale_paid(sale_id):
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            UPDATE sales 
            SET paid = TRUE, 
                payment_status = 'paid',
                updated_at = NOW() 
            WHERE id = %s
        """, (sale_id,))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/sales/<int:sale_id>/mark-delivered', methods=['POST'])
@login_required
def mark_sale_delivered(sale_id):
    try:
        cursor = mysql.connection.cursor()
        
        # First check if sale exists
        cursor.execute("SELECT id FROM sales WHERE id = %s", (sale_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Sale not found'}), 404
            
        cursor.execute("""
            UPDATE sales 
            SET delivery_status = 'delivered',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (sale_id,))
        
        mysql.connection.commit()
        cursor.close()
        
        log_activity(f'Marked sale #{sale_id} as delivered', 'delivery_update')
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error updating delivery status: {str(e)}")
        return jsonify({'success': False, 'message': 'Database error'}), 500

def log_activity(description, activity_type):
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO activity_logs (description, type, user_id) 
            VALUES (%s, %s, %s)
        """, (description, activity_type, session.get('id')))
        mysql.connection.commit()
        cursor.close()
    except Exception as e:
        print(f"Error logging activity: {str(e)}")

@app.route('/reports/export/<format>')
@login_required
def export_report(format):
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Get sales summary
        cursor.execute("""
            SELECT DATE(created_at) as sale_date, 
                   COUNT(*) as total_sales,
                   SUM(total_price) as total_revenue 
            FROM sales 
            GROUP BY DATE(created_at) 
            ORDER BY sale_date DESC 
            LIMIT 10
        """)
        sales_data = cursor.fetchall()
        
        # Get top selling medications
        cursor.execute("""
            SELECT m.name, 
                   COUNT(*) as total_quantity,
                   SUM(s.total_price) as total_revenue
            FROM sales s
            JOIN medications m ON s.medication_id = m.id
            GROUP BY m.id, m.name
            ORDER BY total_quantity DESC
            LIMIT 10
        """)
        top_selling = cursor.fetchall()
        
        cursor.close()

        if format == 'excel':
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                pd.DataFrame(sales_data).to_excel(writer, sheet_name='Sales Summary', index=False)
                pd.DataFrame(top_selling).to_excel(writer, sheet_name='Top Selling', index=False)
            
            output.seek(0)
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='pharmacy_report.xlsx'
            )

        elif format == 'pdf':
            pdf = FPDF()
            pdf.add_page()
            
            # Add title
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, 'Pharmacy Report', 0, 1, 'C')
            
            # Add sales summary
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, 'Sales Summary', 0, 1, 'L')
            pdf.set_font('Arial', '', 12)
            
            # Add table headers
            pdf.cell(60, 10, 'Date', 1)
            pdf.cell(60, 10, 'Sales', 1)
            pdf.cell(60, 10, 'Revenue', 1)
            pdf.ln()
            
            # Add data
            for sale in sales_data:
                pdf.cell(60, 10, str(sale['sale_date']), 1)
                pdf.cell(60, 10, str(sale['total_sales']), 1)
                pdf.cell(60, 10, f"UGX {sale['total_revenue']:,.2f}", 1)
                pdf.ln()
            
            # Save PDF to a temporary file
            temp_pdf = BytesIO()
            pdf.output(dest='F', name='temp.pdf')
            with open('temp.pdf', 'rb') as f:
                temp_pdf.write(f.read())
            temp_pdf.seek(0)
            
            return send_file(
                temp_pdf,
                mimetype='application/pdf',
                as_attachment=True,
                download_name='pharmacy_report.pdf'
            )

        return jsonify({'error': 'Invalid format'}), 400

    except Exception as e:
        print(f"Export error: {str(e)}")
        return jsonify({'error': 'Export failed'}), 500

if __name__ == '__main__':
    app.run(debug=True)
