
import sys
import os
import json
from datetime import datetime

# Add src to path
sys.path.append(os.path.abspath('src'))

from task_manager import TaskManager

def test_done_persistence():
    tm = TaskManager()
    
    # 1. FIND A DONE TASK
    done_task = None
    for page in tm.pages:
        for task in page['tasks']:
            if task['status'] == 'done':
                done_task = task
                break
        if done_task: break
    
    if not done_task:
        print("FAILED: No DONE task found to test.")
        return
    
    original_id = done_task['id']
    print(f"Testing Done Persistence for task: {done_task['name']} ({original_id})")
    
    # 2. EDIT IT (Change name only)
    new_name = done_task['name'] + " (Edited)"
    tm.update_task_details(
        original_id, 
        new_name, 
        done_task['start_time'], 
        done_task['end_time'], 
        done_task['image_path'], 
        done_task['repeat_days']
    )
    
    # 3. RELOAD AND VERIFY
    tm2 = TaskManager()
    updated_task = None
    for page in tm2.pages:
        for task in page['tasks']:
            if task['id'] == original_id:
                updated_task = task
                break
    
    if updated_task['status'] == 'done' and updated_task['name'] == new_name:
        print("SUCCESS: 'Done' status preserved after edit.")
    else:
        print(f"FAILED: 'Done' status became {updated_task['status']}")

def test_prayer_sync_hardening():
    tm = TaskManager()
    print("Testing Prayer Sync Re-enablement...")
    
    # Force prayers to be disabled first
    tm.remove_synced_tasks()
    
    # Run sync (should use fallback/API)
    success = tm.sync_prayer_times()
    
    if success:
        # Check if they are now enabled
        all_enabled = True
        for p in tm.global_prayers.values():
            if not p.get('enabled'):
                all_enabled = False
                break
        
        if all_enabled:
            print("SUCCESS: Prayer tasks re-enabled after sync.")
        else:
            print("FAILED: Prayer tasks remained disabled after sync.")
    else:
        print("FAILED: Prayer sync could not complete (even with fallback).")

if __name__ == "__main__":
    print("--- Starting Application Tests ---")
    test_done_persistence()
    test_prayer_sync_hardening()
    print("--- Tests Complete ---")
