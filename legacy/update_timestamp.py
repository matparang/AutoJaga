#!/usr/bin/env python3
"""
Quick script to update timestamp in heartbeat.md
Demonstrates programmatic file update as step toward automation
"""

import re
from datetime import datetime, timezone

def update_heartbeat_timestamp():
    """Update Last Updated timestamp in heartbeat.md"""
    file_path = "/root/nanojaga/system/monitoring/heartbeat.md"
    
    try:
        # Read current file
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Generate new timestamp (timezone-aware)
        new_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        
        # Find and replace timestamp line
        # Pattern: "Last Updated: YYYY-MM-DD HH:MM UTC"
        pattern = r"Last Updated: \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC"
        
        if re.search(pattern, content):
            # Replace timestamp
            new_content = re.sub(pattern, f"Last Updated: {new_timestamp}", content)
            
            # Write back
            with open(file_path, 'w') as f:
                f.write(new_content)
            
            print(f"✅ Timestamp updated to: {new_timestamp}")
            
            # Verify update
            with open(file_path, 'r') as f:
                updated_content = f.read()
                if new_timestamp in updated_content:
                    print("✅ Verification passed")
                    return True
                else:
                    print("❌ Verification failed")
                    return False
        else:
            print("❌ Timestamp pattern not found in file")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = update_heartbeat_timestamp()
    exit(0 if success else 1)