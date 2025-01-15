import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key'
    
    # MySQL Database Configuration
    MYSQL_HOST = 'localhost'  # MySQL host (use 'localhost' for local testing)
    MYSQL_USER = 'root'  # Replace with your MySQL username
    MYSQL_PASSWORD = '752002'  # Replace with your MySQL password
    MYSQL_DB = 'bkk_pharmacy'  # Name of your MySQL database
    MYSQL_CURSORCLASS = 'DictCursor'  # Return MySQL results as dictionaries

    # Other settings
    DEBUG = True  
