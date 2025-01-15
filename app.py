from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors

app = Flask(__name__)

# Configure MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'your_username'
app.config['MYSQL_PASSWORD'] = 'your_password'
app.config['MYSQL_DB'] = 'bkk_pharmacy'

mysql = MySQL(app)

# Route to display inventory
@app.route('/list_inventory')
def list_inventory():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM inventory")
    inventory = cursor.fetchall()
    return render_template('list_inventory.html', inventory=inventory)

# Route to add new medication
@app.route('/new_medication', methods=['GET', 'POST'])
def new_medication():
    if request.method == 'POST':
        med_name = request.form['med_name']
        med_price = request.form['med_price']
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO inventory (name, price) VALUES (%s, %s)", (med_name, med_price))
        mysql.connection.commit()
        flash('Medication added successfully!')
        return redirect(url_for('list_inventory'))
    return render_template('new_medication.html')

# Route to edit a medication
@app.route('/edit_medication/<int:id>', methods=['GET', 'POST'])
def edit_medication(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch the medication details to pre-fill the form
    cursor.execute('SELECT * FROM inventory WHERE id = %s', (id,))
    medication = cursor.fetchone()
    
    if request.method == 'POST':
        med_name = request.form['med_name']
        med_price = request.form['med_price']
        
        # Update medication in the database
        cursor.execute('UPDATE inventory SET name = %s, price = %s WHERE id = %s', (med_name, med_price, id))
        mysql.connection.commit()
        
        flash('Medication updated successfully!')
        return redirect(url_for('list_inventory'))
    
    return render_template('edit_medication.html', medication=medication)

# Route to delete a medication
@app.route('/delete_medication/<int:id>', methods=['GET'])
def delete_medication(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Delete the medication from the database
    cursor.execute('DELETE FROM inventory WHERE id = %s', (id,))
    mysql.connection.commit()
    
    flash('Medication deleted successfully!')
    return redirect(url_for('list_inventory'))

# Route to add new prescription
@app.route('/new_prescription', methods=['GET', 'POST'])
def new_prescription():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch medications for the dropdown
    cursor.execute("SELECT * FROM inventory")
    medications = cursor.fetchall()
    
    if request.method == 'POST':
        patient_name = request.form['patient_name']
        medication_id = request.form['medication_id']
        quantity = request.form['quantity']
        prescription_date = request.form['prescription_date']
        
        # Insert new prescription into the database
        cursor.execute("INSERT INTO prescriptions (patient_name, medication_id, quantity, prescription_date) VALUES (%s, %s, %s, %s)", 
                       (patient_name, medication_id, quantity, prescription_date))
        mysql.connection.commit()
        
        flash('Prescription added successfully!')
        return redirect(url_for('list_prescriptions'))
    
    return render_template('new_prescription.html', medications=medications)

# Route to list all prescriptions
@app.route('/list_prescriptions')
def list_prescriptions():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch prescriptions along with medication names
    cursor.execute('''
        SELECT prescriptions.id, prescriptions.patient_name, inventory.name AS medication_name, prescriptions.quantity, prescriptions.prescription_date
        FROM prescriptions
        JOIN inventory ON prescriptions.medication_id = inventory.id
    ''')
    prescriptions = cursor.fetchall()
    
    return render_template('list_prescriptions.html', prescriptions=prescriptions)

# Route to edit a prescription
@app.route('/edit_prescription/<int:id>', methods=['GET', 'POST'])
def edit_prescription(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch the current prescription and medication data
    cursor.execute('SELECT * FROM prescriptions WHERE id = %s', (id,))
    prescription = cursor.fetchone()
    
    cursor.execute('SELECT * FROM inventory')
    medications = cursor.fetchall()
    
    if request.method == 'POST':
        patient_name = request.form['patient_name']
        medication_id = request.form['medication_id']
        quantity = request.form['quantity']
        prescription_date = request.form['prescription_date']
        
        # Update the prescription in the database
        cursor.execute('''
            UPDATE prescriptions
            SET patient_name = %s, medication_id = %s, quantity = %s, prescription_date = %s
            WHERE id = %s
        ''', (patient_name, medication_id, quantity, prescription_date, id))
        mysql.connection.commit()
        
        flash('Prescription updated successfully!')
        return redirect(url_for('list_prescriptions'))
    
    return render_template('edit_prescription.html', prescription=prescription, medications=medications)

# Route to delete a prescription
@app.route('/delete_prescription/<int:id>', methods=['GET'])
def delete_prescription(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Delete the prescription from the database
    cursor.execute('DELETE FROM prescriptions WHERE id = %s', (id,))
    mysql.connection.commit()
    
    flash('Prescription deleted successfully!')
    return redirect(url_for('list_prescriptions'))

# Route to display the report page
@app.route('/report', methods=['GET', 'POST'])
def report():
    return render_template('report.html')

# Route to generate a report based on the selected type
@app.route('/generate_report', methods=['POST'])
def generate_report():
    report_type = request.form['report_type']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if report_type == 'inventory':
        # Fetch inventory data
        cursor.execute("SELECT * FROM inventory")
        report_data = cursor.fetchall()
        report_title = "Inventory Report"
    elif report_type == 'prescriptions':
        # Fetch prescription data with medication names
        cursor.execute('''
            SELECT prescriptions.id, prescriptions.patient_name, inventory.name AS medication_name, prescriptions.quantity, prescriptions.prescription_date
            FROM prescriptions
            JOIN inventory ON prescriptions.medication_id = inventory.id
        ''')
        report_data = cursor.fetchall()
        report_title = "Prescription Report"
    
    return render_template('report.html', report_data=report_data, report_type=report_type, report_title=report_title)

if __name__ == '__main__':
    app.secret_key = 'your_secret_key'
    app.run(debug=True)
