import json
import os
import uuid
import threading
import queue
import time
import copy
from datetime import datetime, timedelta
from .api_handler import PrayerTimeHandler

def get_data_file_path():
    """Get persistent path for tasks.json in AppData"""
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    data_dir = os.path.join(appdata, 'DailyTasks')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, 'tasks.json')

DATA_FILE = get_data_file_path()

class TaskManager:
    def __init__(self, data_dir=None):
        self.pages = []  # List of page dicts
        self.global_prayers = {} # Dict of global prayer tasks mapped by ID
        self.prayer_handler = PrayerTimeHandler()

        # Allow tests to override the storage directory
        if data_dir is not None:
            os.makedirs(data_dir, exist_ok=True)
            self._data_file = os.path.join(data_dir, 'tasks.json')
        else:
            self._data_file = DATA_FILE

        # Async Save System
        self._save_queue = queue.Queue()
        self._save_thread = threading.Thread(target=self._save_worker, daemon=True)
        self._save_thread.start()

        self.load_tasks()

    def _save_worker(self):
        """Background thread that writes state to disk without blocking the UI"""
        while True:
            state = self._save_queue.get()
            drained_count = 0
            try:
                # Drain queue to only save the newest state if rapid clicks occurred
                while not self._save_queue.empty():
                    try:
                        state = self._save_queue.get_nowait()
                        drained_count += 1
                    except queue.Empty:
                        break

                temp_file = self._data_file + ".tmp"
                os.makedirs(os.path.dirname(self._data_file), exist_ok=True)
                with open(temp_file, 'w') as f:
                    json.dump(state, f, indent=4)
                if os.path.exists(self._data_file):
                    os.replace(temp_file, self._data_file)
                else:
                    os.rename(temp_file, self._data_file)

            except Exception as e:
                print(f"Async save failed: {e}")
            finally:
                self._save_queue.task_done()
                for _ in range(drained_count):
                    self._save_queue.task_done()


    def save_tasks(self):
        """Queue the current state for asynchronous saving to prevent UI lag"""
        state_copy = {
            'pages': copy.deepcopy(self.pages),
            'global_prayers': copy.deepcopy(self.global_prayers)
        }
        self._save_queue.put(state_copy)

    # ═══════════════════════════════════════════════════════════
    # PAGE MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def get_pages(self):
        """Return list of page metadata (id, name, muted, order)"""
        return [
            {
                'id': p['id'],
                'name': p['name'],
                'muted': p.get('muted', False),
                'order': p.get('order', i)
            }
            for i, p in enumerate(self.pages)
        ]

    def add_page(self, name):
        """Create a new page and return it"""
        page = {
            'id': str(uuid.uuid4()),
            'name': name,
            'muted': False,
            'order': len(self.pages),
            'tasks': []
        }
        self.pages.append(page)
        self.save_tasks()
        return page

    def rename_page(self, page_id, new_name):
        """Rename a page"""
        for page in self.pages:
            if page['id'] == page_id:
                page['name'] = new_name
                self.save_tasks()
                return True
        return False

    def delete_page(self, page_id):
        """Delete a page and all its tasks"""
        self.pages = [p for p in self.pages if p['id'] != page_id]
        # Re-order remaining pages
        for i, p in enumerate(self.pages):
            p['order'] = i
        self.save_tasks()

    def toggle_mute(self, page_id):
        """Toggle mute state for a page. Returns new mute state."""
        for page in self.pages:
            if page['id'] == page_id:
                page['muted'] = not page.get('muted', False)
                self.save_tasks()
                return page['muted']
        return False

    def _find_page(self, page_id):
        """Internal helper to find a page by ID"""
        for page in self.pages:
            if page['id'] == page_id:
                return page
        return None

    def get_default_page_id(self):
        """Get the first page's ID, creating one if none exist"""
        if not self.pages:
            page = self.add_page("My Routine")
            return page['id']
        return self.pages[0]['id']

    def reorder_pages(self, new_order_ids):
        """Reorder pages based on a list of page IDs mapping"""
        page_dict = {p['id']: p for p in self.pages}
        new_pages = []
        for pid in new_order_ids:
            if pid in page_dict:
                new_pages.append(page_dict[pid])
        
        # Fallback safeguard in case logic dropped any
        for p in self.pages:
            if p['id'] not in new_order_ids:
                new_pages.append(p)
                
        self.pages = new_pages
        # Update json order map natively
        for i, p in enumerate(self.pages):
            p['order'] = i
            
        self.save_tasks()

    # ═══════════════════════════════════════════════════════════
    # DATA PERSISTENCE
    # ═══════════════════════════════════════════════════════════

    def load_tasks(self):
        if os.path.exists(self._data_file):
            try:
                with open(self._data_file, 'r') as f:
                    data = json.load(f)

                # ── Migration: old flat list → new pages structure ──
                if isinstance(data, list):
                    print("Migrating flat task list to page-based structure...")
                    clean = [t for t in data if isinstance(t, dict)]
                    self.pages = [{
                        'id': str(uuid.uuid4()),
                        'name': 'My Routine',
                        'muted': False,
                        'order': 0,
                        'tasks': clean
                    }]
                    self.save_tasks()  # Save in new format immediately
                    return

                # ── New format: dict with 'pages' key ──
                if isinstance(data, dict) and 'pages' in data:
                    pages = data['pages']
                    self.global_prayers = data.get('global_prayers', {})
                    if not isinstance(pages, list):
                        raise ValueError(f"Expected pages list, got {type(pages).__name__}")

                    # Validate each page and migrate prayers out
                    clean_pages = []
                    for p in pages:
                        if not isinstance(p, dict):
                            continue
                        tasks = p.get('tasks', [])
                        if not isinstance(tasks, list):
                            tasks = []

                        clean_tasks = []
                        for t in tasks:
                            if not isinstance(t, dict): continue

                            # Migrate synced prayers to global
                            if t.get('is_synced', False) or t.get('name') in ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']:
                                global_id = f"global_{t['name']}"
                                t['id'] = global_id
                                if global_id not in self.global_prayers:
                                    self.global_prayers[global_id] = t
                            else:
                                clean_tasks.append(t)

                        p['tasks'] = clean_tasks
                        clean_pages.append(p)

                    self.pages = clean_pages
                else:
                    raise ValueError(f"Unrecognized data format")

            except (json.JSONDecodeError, ValueError) as e:
                print(f"Task file corrupt ({e}). Backing up and resetting.")
                backup_path = self._data_file + ".bak"
                try:
                    import shutil
                    shutil.copy2(self._data_file, backup_path)
                except Exception:
                    pass
                self.pages = []
                self.global_prayers = {}
        else:
            self.pages = []
            self.global_prayers = {}


    def add_task(self, name, start_time, end_time, image_path=None, is_synced=False, enabled=True, repeat_days=None, page_id=None):
        if repeat_days is None:
            repeat_days = [0,1,2,3,4,5,6]

        # Find target page
        if page_id is None:
            page_id = self.get_default_page_id()
        
        page = self._find_page(page_id)
        if page is None:
            page = self._find_page(self.get_default_page_id())

        new_task = {
            "id": str(uuid.uuid4()),
            "name": name,
            "start_time": start_time,
            "end_time": end_time,
            "image_path": image_path,
            "repeat_days": repeat_days,
            "status": "pending",
            "is_synced": is_synced,
            "enabled": enabled,
            "created_at": datetime.now().isoformat()
        }
        page['tasks'].append(new_task)

        # Immediately apply state consistency
        self.check_state_consistency(new_task)

        self.save_tasks()
        return new_task

    def update_task_status(self, task_id, status):
        task_id = str(task_id)
        if task_id.startswith('global_') and task_id in self.global_prayers:
            t = self.global_prayers[task_id]
            t['status'] = status
            if status == 'done':
                t['completed_at'] = datetime.now().isoformat()
            self.save_tasks()
            return True
            
        for page in self.pages:
            for task in page['tasks']:
                if task['id'] == task_id:
                    task['status'] = status
                    if status == 'done':
                        task['completed_at'] = datetime.now().isoformat()
                    self.save_tasks()
                    return True
        return False

    def update_task_details(self, task_id, name, start_time, end_time, image_path=None, repeat_days=None):
        task_id = str(task_id)
        if task_id.startswith('global_') and task_id in self.global_prayers:
            task = self.global_prayers[task_id]
            task['name'] = name
            task['start_time'] = start_time
            task['end_time'] = end_time
            task['image_path'] = image_path
            if repeat_days is not None:
                task['repeat_days'] = repeat_days
            if task['status'] == 'failed':
                task['status'] = 'pending'
            self.save_tasks()
            return True
            
        for page in self.pages:
            for task in page['tasks']:
                if task['id'] == task_id:
                    task['name'] = name
                    task['start_time'] = start_time
                    task['end_time'] = end_time
                    task['image_path'] = image_path
                    if repeat_days is not None:
                        task['repeat_days'] = repeat_days
                    if task['status'] == 'failed':
                        task['status'] = 'pending'
                    self.save_tasks()
                    return True
        return False

    def check_state_consistency(self, task):
        """
        Enforce strict state machine rules based on current time.
        Returns: (new_status, changed_bool)
        """
        now = datetime.now()

        # Disabled & Ghost Check
        repeat_days = task.get('repeat_days', [0,1,2,3,4,5,6])
        if len(repeat_days) == 0:
            if task.get('status') != 'disabled':
                task['status'] = 'disabled'
                self.save_tasks()
                return 'disabled', True
            return 'disabled', False

        if now.weekday() not in repeat_days:
            if task.get('status') in ['active', 'failed']:
                task['status'] = 'pending'
                self.save_tasks()
                return 'pending', True
            return task.get('status', 'pending'), False

        try:
            start_dt = datetime.combine(now.date(), datetime.strptime(task['start_time'], "%H:%M").time())
            end_dt = datetime.combine(now.date(), datetime.strptime(task['end_time'], "%H:%M").time())
        except ValueError:
            return task['status'], False

        # Midnight Handling
        if end_dt < start_dt:
            if now.hour < 12:
                start_dt -= timedelta(days=1)
            else:
                end_dt += timedelta(days=1)

        current_status = task.get('status', 'pending')
        new_status = current_status

        if current_status == 'done':
            return 'done', False

        if now < start_dt:
            if current_status in ['active', 'failed']:
                new_status = 'pending'
        elif start_dt <= now <= end_dt:
            if current_status in ['pending', 'failed']:
                new_status = 'active'
        elif now > end_dt:
            if current_status in ['pending', 'active']:
                new_status = 'failed'

        if new_status != current_status:
            task['status'] = new_status
            self.save_tasks()
            return new_status, True

        return current_status, False

    def delete_task(self, task_id):
        task_id = str(task_id)
        if task_id.startswith('global_') and task_id in self.global_prayers:
            del self.global_prayers[task_id]
            self.save_tasks()
            return
            
        for page in self.pages:
            page['tasks'] = [t for t in page['tasks'] if str(t['id']) != task_id]
        self.save_tasks()

    def get_tasks(self, page_id=None):
        """
        Get tasks. If page_id is provided, return only that page's tasks + global prayers.
        If None, return ALL tasks across all pages (for background monitoring).
        """
        tasks_out = []
        if page_id is not None:
            page = self._find_page(page_id)
            if page:
                tasks_out = [t for t in page['tasks'] if isinstance(t, dict) and t.get('enabled', True)]
            
            # Append global prayers
            tasks_out += [t for t in self.global_prayers.values() if isinstance(t, dict) and t.get('enabled', True)]
            return tasks_out
        
        # All tasks across all pages
        for page in self.pages:
            for t in page['tasks']:
                if isinstance(t, dict) and t.get('enabled', True):
                    tasks_out.append(t)
        
        tasks_out += [t for t in self.global_prayers.values() if isinstance(t, dict) and t.get('enabled', True)]
        return tasks_out

    def get_task_by_id(self, task_id):
        """Return a single task dict by its ID, or None if not found."""
        str_id = str(task_id)
        # Check global prayers first (fast path)
        if str_id.startswith('global_'):
            return self.global_prayers.get(str_id)
        # Search page tasks
        for page in self.pages:
            for task in page['tasks']:
                if str(task.get('id', '')) == str_id:
                    return task
        return None

    def get_tasks_for_monitoring(self):
        """Get all tasks from non-muted pages + global prayers (for notifications/sounds)"""
        tasks = []
        for page in self.pages:
            if page.get('muted', False):
                continue  # Skip muted pages entirely
            for t in page['tasks']:
                if isinstance(t, dict) and t.get('enabled', True):
                    tasks.append(t)
                    
        tasks += [t for t in self.global_prayers.values() if isinstance(t, dict) and t.get('enabled', True)]
        return tasks

    def is_task_on_muted_page(self, task_id):
        """Check if a task belongs to a muted page"""
        if str(task_id).startswith('global_'):
            return False # Prayers remain active universally
            
        for page in self.pages:
            for task in page['tasks']:
                if str(task.get('id')) == str(task_id):
                    return page.get('muted', False)
        return False

    # ═══════════════════════════════════════════════════════════
    # PRAYER TIMES (operates on default page)
    # ═══════════════════════════════════════════════════════════

    def sync_prayer_times(self, location_data=None, page_id=None):
        prayers = self.prayer_handler.get_prayer_times()
        if not prayers:
            return False

        prayer_list = []
        ordered_names = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']

        for name in ordered_names:
            if name in prayers:
                prayer_list.append((name, prayers[name]))

        if not prayer_list:
            print("Sync failed: No matching prayer names found in API response.")
            return False

        PRAYER_ICONS = {
            'Fajr': '🌅',
            'Dhuhr': '☀️',
            'Asr': '🌤️',
            'Maghrib': '🌇',
            'Isha': '🌙'
        }

        for i in range(len(prayer_list)):
            name, start_t = prayer_list[i]

            if name == 'Fajr' and 'Sunrise' in prayers:
                end_t = prayers['Sunrise']
            elif i < len(prayer_list) - 1:
                next_name, next_start = prayer_list[i+1]
                end_t = next_start
            else:
                end_t = "23:59"

            icon = PRAYER_ICONS.get(name, '🕌')
            global_id = f"global_{name}"

            if global_id in self.global_prayers:
                self.global_prayers[global_id].update({
                    'start_time': start_t,
                    'end_time': end_t,
                    'image_path': icon,
                    'is_synced': True,
                    'enabled': True
                })
            else:
                self.global_prayers[global_id] = {
                    "id": global_id,
                    "name": name,
                    "start_time": start_t,
                    "end_time": end_t,
                    "image_path": icon,
                    "repeat_days": [0,1,2,3,4,5,6],
                    "status": "pending",
                    "is_synced": True,
                    "enabled": True,
                    "created_at": datetime.now().isoformat()
                }

        self.save_tasks()
        return True

    def remove_synced_tasks(self, page_id=None):
        """Hide/Disable synced tasks globally"""
        for t in self.global_prayers.values():
            t['enabled'] = False
        self.save_tasks()
        
    def _iter_all_stored_tasks(self):
        """Yields all tasks across all pages and global prayers for synchronization."""
        for page in self.pages:
            yield from page['tasks']
        yield from self.global_prayers.values()

    def check_daily_reset(self):
        """Delegate to reset_daily_tasks for backward-compatibility."""
        self.reset_daily_tasks()

    def reset_daily_tasks(self):
        """Reset task statuses to 'pending' for the new day across ALL tasks."""
        from datetime import datetime, timedelta
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        for task in self._iter_all_stored_tasks():
            # SAFETY: If completed TODAY, do not reset
            if task.get('status') == 'done':
                completed_at = task.get('completed_at')
                if completed_at and completed_at.startswith(today_str):
                    continue

            # Check overnight tasks
            try:
                start_dt = datetime.combine(now.date(), datetime.strptime(task['start_time'], "%H:%M").time())
                end_dt = datetime.combine(now.date(), datetime.strptime(task['end_time'], "%H:%M").time())

                if end_dt < start_dt:
                    if now.hour < 12:
                        start_dt -= timedelta(days=1)
                    else:
                        end_dt += timedelta(days=1)

                if start_dt <= now <= end_dt and task['status'] == 'active':
                    continue
            except (ValueError, KeyError):
                pass

            task['status'] = 'pending'
            task.pop('completed_at', None)

        self.save_tasks()

    def synchronize_task_statuses(self):
        """
        Synchronize all task statuses based on current time across ALL tasks.
        Returns (modified, changes) where changes is a list of
        (task_dict, old_status, new_status) tuples for every transition.
        """
        from datetime import datetime, timedelta

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        modified = False
        changes = []  # [(task, old_status, new_status), ...]

        for task in self._iter_all_stored_tasks():
            if not task.get('enabled', True):
                continue

            current_status = task.get('status', 'pending')

            if current_status == 'done':
                continue

            start_str = task.get('start_time', '00:00')
            end_str = task.get('end_time', '23:59')

            try:
                start_dt = datetime.strptime(f"{today_str} {start_str}", "%Y-%m-%d %H:%M")
                end_dt = datetime.strptime(f"{today_str} {end_str}", "%Y-%m-%d %H:%M")
            except ValueError:
                continue

            repeat_days = task.get('repeat_days', [0,1,2,3,4,5,6])
            current_weekday = now.weekday()

            if len(repeat_days) == 0:
                new_status = 'disabled'
            elif current_weekday not in repeat_days:
                new_status = 'pending'
            else:
                # Midnight handling: consistent with check_state_consistency
                if end_dt < start_dt:
                    if now.hour < 12:
                        start_dt -= timedelta(days=1)
                    else:
                        end_dt += timedelta(days=1)

                if start_dt <= now <= end_dt:
                    new_status = 'active'
                elif now < start_dt:
                    new_status = 'pending'
                else:
                    new_status = 'failed'

            if current_status != new_status:
                task['status'] = new_status
                modified = True
                changes.append((task, current_status, new_status))

        if modified:
            self.save_tasks()

        return modified, changes

    def import_tasks_as_page(self, page_name, tasks):
        """Import decoded tasks as a brand new page. Returns the new page."""
        page = self.add_page(page_name)
        
        # Ensure fresh state computation based purely on current time
        for task in tasks:
            # Overwrite imported legacy status/timestamps with fresh defaults
            task['status'] = 'pending'
            if 'completed_at' in task:
                del task['completed_at']
                
            self.check_state_consistency(task)
            
        page['tasks'] = tasks
        self.save_tasks()
        return page
