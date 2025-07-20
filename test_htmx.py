#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
import tempfile
import sqlite3

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
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash('testpass')
        conn.execute(
            'INSERT INTO user (mail, password_hash) VALUES (?, ?)',
            ('test@example.com', password_hash)
        )
        
        # Insert test vacation
        conn.execute(
            'INSERT INTO vacation (user_id, start_date, end_date) VALUES (?, ?, ?)',
            (1, '2025-08-01', '2025-08-05')
        )
        
        conn.commit()
    
    return db_path

def test_htmx_endpoints():
    """Test HTMX endpoints"""
    
    # Create test database
    db_path = create_test_db()
    
    # Update app config to use test database
    app.config['TESTING'] = True
    app.config['DB_PATH'] = db_path
    
    with app.test_client() as client:
        # Test login
        response = client.post('/login', data={
            'email': 'test@example.com',
            'password': 'testpass'
        })
        print(f"Login response: {response.status_code}")
        
        # Test vacation table endpoint
        response = client.get('/vacation_table', headers={'HX-Request': 'true'})
        print(f"Vacation table HTMX response: {response.status_code}")
        print(f"Response contains table: {'table' in response.get_data(as_text=True)}")
        
        # Test add vacation form endpoint
        response = client.get('/add_vacation', headers={'HX-Request': 'true'})
        print(f"Add vacation form HTMX response: {response.status_code}")
        print(f"Response contains form: {'form' in response.get_data(as_text=True)}")
        
        # Test add vacation POST
        response = client.post('/add_vacation', 
                             data={'start_date': '2025-09-01', 'end_date': '2025-09-05'},
                             headers={'HX-Request': 'true'})
        print(f"Add vacation POST HTMX response: {response.status_code}")
        
    # Clean up
    os.close(db_fd)
    os.unlink(db_path)
    
    print("HTMX endpoints test completed!")

if __name__ == '__main__':
    test_htmx_endpoints()
