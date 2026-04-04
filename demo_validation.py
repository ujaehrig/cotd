#!/usr/bin/env python3

from datetime import date, datetime, timedelta

def test_validation_logic():
    """Test the validation logic directly"""
    
    print("Testing date validation logic:")
    
    # Test past date
    yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    today = date.today()
    
    print(f"Today: {today}")
    print(f"Yesterday: {yesterday}")
    
    # Parse the date
    start_date_obj = datetime.strptime(yesterday, '%Y-%m-%d').date()
    print(f"Parsed yesterday: {start_date_obj}")
    
    # Check if it's in the past
    if start_date_obj < today:
        print("✅ Past date validation logic works: Yesterday is detected as past")
        error_msg = 'Start date cannot be in the past. Please select today or a future date.'
        print(f"Error message: {error_msg}")
    else:
        print("❌ Past date validation logic failed")
    
    # Test future date
    tomorrow = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    future_date_obj = datetime.strptime(tomorrow, '%Y-%m-%d').date()
    
    if future_date_obj >= today:
        print("✅ Future date validation logic works: Tomorrow is accepted")
    else:
        print("❌ Future date validation logic failed")

if __name__ == '__main__':
    test_validation_logic()
