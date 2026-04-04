#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#     "flask>=2.3.0",
#     "flask-login>=0.6.0",
#     "werkzeug>=2.3.0",
#     "requests>=2.25.0",
#     "python-dotenv>=1.0.0"
# ]
# ///

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import check_vacation_overlap, check_duplicate_vacation
from manage_vacations import get_db_connection, add_vacation, delete_vacation
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_vacation_validation():
    """Test vacation overlap and duplicate validation"""
    
    print("Testing Vacation Validation")
    print("=" * 40)
    
    # Test user ID (assuming user 1 exists)
    test_user_id = 1
    
    # Clean up any existing test vacations first
    print("Cleaning up existing test vacations...")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM vacation WHERE user_id = ? AND start_date >= '2025-12-01'", (test_user_id,))
            conn.commit()
    except Exception as e:
        print(f"Cleanup error (expected if no test data): {e}")
    
    # Test 1: Add initial vacation
    print("\n1. Adding initial vacation: 2025-12-10 to 2025-12-15")
    try:
        add_vacation(test_user_id, "2025-12-10", "2025-12-15")
        print("✓ Initial vacation added successfully")
    except Exception as e:
        print(f"✗ Error adding initial vacation: {e}")
        return
    
    # Test 2: Check for exact duplicate
    print("\n2. Testing exact duplicate detection...")
    is_duplicate, error_msg = check_duplicate_vacation(test_user_id, "2025-12-10", "2025-12-15")
    if is_duplicate:
        print(f"✓ Duplicate detected: {error_msg}")
    else:
        print("✗ Duplicate not detected (should have been)")
    
    # Test 3: Check for overlap - starts before, ends during
    print("\n3. Testing overlap detection (starts before, ends during)...")
    has_overlap, error_msg = check_vacation_overlap(test_user_id, "2025-12-08", "2025-12-12")
    if has_overlap:
        print(f"✓ Overlap detected: {error_msg}")
    else:
        print("✗ Overlap not detected (should have been)")
    
    # Test 4: Check for overlap - starts during, ends after
    print("\n4. Testing overlap detection (starts during, ends after)...")
    has_overlap, error_msg = check_vacation_overlap(test_user_id, "2025-12-12", "2025-12-18")
    if has_overlap:
        print(f"✓ Overlap detected: {error_msg}")
    else:
        print("✗ Overlap not detected (should have been)")
    
    # Test 5: Check for overlap - completely contains existing
    print("\n5. Testing overlap detection (completely contains existing)...")
    has_overlap, error_msg = check_vacation_overlap(test_user_id, "2025-12-08", "2025-12-18")
    if has_overlap:
        print(f"✓ Overlap detected: {error_msg}")
    else:
        print("✗ Overlap not detected (should have been)")
    
    # Test 6: Check for overlap - completely contained within existing
    print("\n6. Testing overlap detection (completely contained within existing)...")
    has_overlap, error_msg = check_vacation_overlap(test_user_id, "2025-12-12", "2025-12-14")
    if has_overlap:
        print(f"✓ Overlap detected: {error_msg}")
    else:
        print("✗ Overlap not detected (should have been)")
    
    # Test 7: Check for no overlap - before existing
    print("\n7. Testing no overlap (before existing vacation)...")
    has_overlap, error_msg = check_vacation_overlap(test_user_id, "2025-12-05", "2025-12-08")
    if not has_overlap:
        print("✓ No overlap detected (correct)")
    else:
        print(f"✗ False overlap detected: {error_msg}")
    
    # Test 8: Check for no overlap - after existing
    print("\n8. Testing no overlap (after existing vacation)...")
    has_overlap, error_msg = check_vacation_overlap(test_user_id, "2025-12-17", "2025-12-20")
    if not has_overlap:
        print("✓ No overlap detected (correct)")
    else:
        print(f"✗ False overlap detected: {error_msg}")
    
    # Test 9: Add second vacation and test multiple overlaps
    print("\n9. Adding second vacation and testing multiple overlaps...")
    try:
        add_vacation(test_user_id, "2025-12-25", "2025-12-25")  # Single day
        print("✓ Second vacation added successfully")
        
        # Test overlap with multiple existing vacations
        has_overlap, error_msg = check_vacation_overlap(test_user_id, "2025-12-12", "2025-12-26")
        if has_overlap:
            print(f"✓ Multiple overlaps detected: {error_msg}")
        else:
            print("✗ Multiple overlaps not detected (should have been)")
            
    except Exception as e:
        print(f"✗ Error adding second vacation: {e}")
    
    # Cleanup
    print("\n10. Cleaning up test data...")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM vacation WHERE user_id = ? AND start_date >= '2025-12-01'", (test_user_id,))
            conn.commit()
        print("✓ Test data cleaned up")
    except Exception as e:
        print(f"✗ Cleanup error: {e}")
    
    print("\nValidation test completed!")

if __name__ == '__main__':
    test_vacation_validation()
