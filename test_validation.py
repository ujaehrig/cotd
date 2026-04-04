#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from datetime import date, timedelta
import tempfile
import sqlite3
from werkzeug.security import generate_password_hash

def create_test_db():
    """Create a temporary test database with sample data"""
    db_fd, db_path = tempfile.mkstemp()
    
    with sqlite3.connect(db_path) as conn:
        # Create tables
        conn.execute('''
            CREATE TABLE user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mail TEXT UNIQUE NOT NULL,
                weekdays TEXT DEFAULT "0,1,2,3,4",
                last_chosen DATE,
                password_hash TEXT,
                password_reset_required INTEGER DEFAULT 0
            )
        ''')
        
        conn.execute('''
            CREATE TABLE vacation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                FOREIGN KEY (user_id) REFERENCES user (id)
            )
        ''')
        
        # Insert test user
        password_hash = generate_password_hash('testpass')
        conn.execute(
            'INSERT INTO user (mail, password_hash) VALUES (?, ?)',
            ('test@example.com', password_hash)
        )
        
        conn.commit()
    
    return db_fd, db_path

def test_past_date_validation():
    """Test that past dates are properly rejected with clear error messages"""
    
    # Create test database
    db_fd, db_path = create_test_db()
    
    # Update app config to use test database
    app.config['TESTING'] = True
    app.config['DB_PATH'] = db_path
    
    with app.test_client() as client:
        # Login first
        login_response = client.post('/login', data={
            'email': 'test@example.com',
            'password': 'testpass'
        })
        print(f"Login status: {login_response.status_code}")
        
        # Test with past date
        yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        print(f"Testing with past date: {yesterday}")
        
        # Test HTMX request with past date
        response = client.post('/add_vacation', 
                             data={'start_date': yesterday},
                             headers={'HX-Request': 'true'})
        
        print(f"Response status: {response.status_code}")
        response_text = response.get_data(as_text=True)
        print(f"Response data: {response_text}")
        
        # Check if the response contains the expected error message
        if 'Start date cannot be in the past' in response_text:
            print("✅ Past date validation working correctly!")
        else:
            print("❌ Past date validation not working as expected")
        
        # Test with future date (should work)
        tomorrow = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"\nTesting with future date: {tomorrow}")
        
        response = client.post('/add_vacation', 
                             data={'start_date': tomorrow},
                             headers={'HX-Request': 'true'})
        
        print(f"Response status: {response.status_code}")
        response_text = response.get_data(as_text=True)
        
        if response.status_code == 200 and 'table' in response_text:
            print("✅ Future date accepted and table updated!")
        else:
            print(f"Response data: {response_text}")
    
    # Clean up
    os.close(db_fd)
    os.unlink(db_path)

if __name__ == '__main__':
    test_past_date_validation()
