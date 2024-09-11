# backend/config.py
import os
import binascii

class Config:
    SECRET_KEY = binascii.hexlify(os.urandom(24)).decode()

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    DATABASE_PATH = os.path.join(BASE_DIR, 'flask_data.db')
    
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
