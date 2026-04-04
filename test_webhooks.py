#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#     "requests>=2.25.0",
#     "python-dotenv>=1.0.0"
# ]
# ///

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vacation_webhooks import send_vacation_added_webhook, send_vacation_deleted_webhook
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_vacation_webhooks():
    """Test vacation webhook functionality"""
    
    print("Testing Vacation Webhooks")
    print("=" * 40)
    
    # Test data
    user_email = "test@example.com"
    start_date = "2025-08-01"
    end_date = "2025-08-05"
    
    # Check if webhook URLs are configured
    added_webhook = os.environ.get("VACATION_ADDED_WEBHOOK_URL")
    deleted_webhook = os.environ.get("VACATION_DELETED_WEBHOOK_URL")
    
    print(f"VACATION_ADDED_WEBHOOK_URL: {'✓ Configured' if added_webhook else '✗ Not configured'}")
    print(f"VACATION_DELETED_WEBHOOK_URL: {'✓ Configured' if deleted_webhook else '✗ Not configured'}")
    print()
    
    if not added_webhook and not deleted_webhook:
        print("No webhook URLs configured. Add them to your .env file to test:")
        print("VACATION_ADDED_WEBHOOK_URL=https://hooks.slack.com/workflows/...")
        print("VACATION_DELETED_WEBHOOK_URL=https://hooks.slack.com/workflows/...")
        print()
        print("Example webhook payload that would be sent:")
        print({
            "event": "vacation_added",
            "user_email": user_email,
            "start_date": start_date,
            "end_date": end_date,
            "duration_days": "5",
            "timestamp": "2025-07-20T15:00:00",
            "message": f"{user_email} added vacation: {start_date} to {end_date} (5 days)"
        })
        return
    
    # Test vacation added webhook
    if added_webhook:
        print("Testing vacation added webhook...")
        try:
            success = send_vacation_added_webhook(user_email, start_date, end_date)
            print(f"Vacation added webhook: {'✓ Success' if success else '✗ Failed'}")
        except Exception as e:
            print(f"Vacation added webhook: ✗ Error - {e}")
    
    # Test vacation deleted webhook
    if deleted_webhook:
        print("Testing vacation deleted webhook...")
        try:
            success = send_vacation_deleted_webhook(user_email, start_date, end_date)
            print(f"Vacation deleted webhook: {'✓ Success' if success else '✗ Failed'}")
        except Exception as e:
            print(f"Vacation deleted webhook: ✗ Error - {e}")
    
    print()
    print("Webhook test completed!")

if __name__ == '__main__':
    test_vacation_webhooks()
