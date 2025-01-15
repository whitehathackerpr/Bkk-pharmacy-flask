from flask import Flask
from flask_mysqldb import MySQL

app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '752002'
app.config['MYSQL_DB'] = 'bkk_pharmacy'

# Initialize MySQL
mysql = MySQL(app)
