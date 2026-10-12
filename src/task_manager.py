import json
import os
import uuid
import threading
import queue
import time
import copy
from datetime import datetime, timedelta

_TIME_SECS_CACHE = {}


def _parse_hhmm_to_secs(t_str):
    """Fast O(1) cached parser converting 'HH:MM' to seconds from midnight (0..86340)."""
    cached = _TIME_SECS_CACHE.get(t_str)
    if cached is not None:
        return cached
    if not isinstance(t_str, str) or ":" not in t_str:
        raise ValueError("Invalid time string")
    parts = t_str.split(":")
    if len(parts) != 2:
        raise ValueError("Invalid time format")
    h = int(parts[0])
    m = int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Time out of range")
    secs = (h * 60 + m) * 60
    if len(_TIME_SECS_CACHE) < 1500:
        _TIME_SECS_CACHE[t_str] = secs
    return secs


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
        self._prayer_handler = None

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

    @property
    def prayer_handler(self):
        if self._prayer_handler is None:
            from .api_handler import PrayerTimeHandler
            self._prayer_handler = PrayerTimeHandler()
        return self._prayer_handler

    @prayer_handler.setter
    def prayer_handler(self, value):
        self._prayer_handler = value

    def _schedule_cache_cleanup(self):
        """Enqueue an asynchronous orphan-cache cleanup on the background worker thread."""
        self._save_queue.put("__CLEANUP_CACHE__")

    def _save_worker(self):
        """Background thread that writes state to disk and prunes orphaned cache files without blocking the UI."""
        import shutil
        while True:
            item = self._save_queue.get()
            drained_count = 0
            run_cleanup = (item == "__CLEANUP_CACHE__")
            state = None if run_cleanup else item
            try:
                # Drain queue to coalesce rapid consecutive saves and cleanup flags
                while not self._save_queue.empty():
                    try:
                        nxt = self._save_queue.get_nowait()
                        drained_count += 1
                        if nxt == "__CLEANUP_CACHE__":
                            run_cleanup = True
                        else:
                            state = nxt
                    except queue.Empty:
                        break

                if state is not None:
                    temp_file = f"{self._data_file}.{threading.get_ident()}.tmp"
                    bak_file = self._data_file + ".bak"
                    os.makedirs(os.path.dirname(self._data_file), exist_ok=True)
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(state, f, separators=(',', ':'))
                        f.flush()

                    if os.path.exists(self._data_file):
                        try:
                            if os.path.getsize(self._data_file) > 2:
                                shutil.copy2(self._data_file, bak_file)
                        except OSError:
                            pass
                    for attempt in range(4):
                        try:
                            os.replace(temp_file, self._data_file)
                            break
                        except PermissionError:
                            if attempt == 3:
                                raise
                            time.sleep(0.015)

                if run_cleanup:
                    self.cleanup_orphaned_cache_images()

            except Exception as e:
                print(f"Async save failed: {e}")
            finally:
                if 'temp_file' in locals() and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass
                self._save_queue.task_done()
                for _ in range(drained_count):
                    self._save_queue.task_done()




    def save_tasks(self):
        """Queue a lightweight snapshot of the current state for asynchronous saving"""
        state_copy = {
            'pages': [
                {
                    **p,
                    'tasks': [
                        {**t, 'repeat_days': list(t['repeat_days'])} if 'repeat_days' in t else dict(t)
                        for t in p.get('tasks', ())
                    ]
                }
                for p in self.pages
            ],
            'global_prayers': {
                k: ({**v, 'repeat_days': list(v['repeat_days'])} if 'repeat_days' in v else dict(v))
                for k, v in self.global_prayers.items()
            }
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
        self._schedule_cache_cleanup()

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
    # DATA PERSISTENCE & CACHE HYGIENE
    # ═══════════════════════════════════════════════════════════

    def _apply_loaded_data(self, data):
        """Validate and apply parsed JSON data into self.pages and self.global_prayers."""
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
            self.global_prayers = {}
            self.save_tasks()  # Save in new format immediately
            return

        # ── New format: dict with 'pages' key ──
        if isinstance(data, dict) and 'pages' in data:
            pages = data['pages']
            global_prayers = data.get('global_prayers', {})
            if not isinstance(pages, list):
                raise ValueError(f"Expected pages list, got {type(pages).__name__}")
            if not isinstance(global_prayers, dict):
                global_prayers = {}
            self.global_prayers = global_prayers

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
                    if not isinstance(t, dict):
                        continue

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
            raise ValueError("Unrecognized data format")

    def load_tasks(self):
        bak_path = self._data_file + ".bak"
        if os.path.exists(self._data_file):
            try:
                with open(self._data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._apply_loaded_data(data)
                self._schedule_cache_cleanup()
                return
            except (json.JSONDecodeError, ValueError, OSError) as e:
                print(f"Task file corrupt ({e}). Attempting recovery from backup...")
                corrupt_path = self._data_file + ".corrupt"
                try:
                    import shutil
                    shutil.copy2(self._data_file, corrupt_path)
                except Exception:
                    pass

                # Attempt recovery from last-known-good .bak file
                if os.path.exists(bak_path):
                    try:
                        with open(bak_path, 'r', encoding='utf-8') as bf:
                            bak_data = json.load(bf)
                        self._apply_loaded_data(bak_data)
                        self.save_tasks()
                        print("Successfully recovered tasks from backup (.bak).")
                        self._schedule_cache_cleanup()
                        return
                    except Exception as bak_err:
                        print(f"Backup recovery failed ({bak_err}). Resetting to empty state.")

                self.pages = []
                self.global_prayers = {}
        elif os.path.exists(bak_path):
            try:
                with open(bak_path, 'r', encoding='utf-8') as bf:
                    bak_data = json.load(bf)
                self._apply_loaded_data(bak_data)
                self.save_tasks()
                self._schedule_cache_cleanup()
                return
            except Exception:
                self.pages = []
                self.global_prayers = {}
        else:
            self.pages = []
            self.global_prayers = {}

    def cleanup_orphaned_cache_images(self):
        """
        Scan the DailyTasks/cache directory and remove orphaned custom_* image files
        whose parent tasks were deleted or had their icon replaced.
        Returns the number of deleted orphaned files.
        """
        try:
            cache_dir = os.path.join(os.path.dirname(self._data_file), 'cache')
            if not os.path.isdir(cache_dir):
                return 0

            referenced_basenames = set()
            for page in self.pages:
                for task in page.get('tasks', ()):
                    img = task.get('image_path')
                    if img and isinstance(img, str):
                        referenced_basenames.add(os.path.basename(img))

            for task in self.global_prayers.values():
                if isinstance(task, dict):
                    img = task.get('image_path')
                    if img and isinstance(img, str):
                        referenced_basenames.add(os.path.basename(img))

            removed = 0
            for fname in os.listdir(cache_dir):
                if not fname.startswith('custom_'):
                    continue
                if fname not in referenced_basenames:
                    fpath = os.path.join(cache_dir, fname)
                    try:
                        if os.path.isfile(fpath):
                            os.remove(fpath)
                            removed += 1
                    except OSError:
                        pass
            return removed
        except Exception as e:
            print(f"Cache cleanup warning: {e}")
            return 0


    def add_task(self, name, start_time=None, end_time=None, image_path=None, is_synced=False, enabled=True, repeat_days=None, page_id=None):
        if repeat_days is None:
            repeat_days = [0,1,2,3,4,5,6]
        if not start_time:
            start_time = None
            end_time = None
        elif not end_time:
            end_time = None

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

        # Immediately apply state consistency without triggering redundant save
        self.check_state_consistency(new_task, save=False)

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
        if not start_time:
            start_time = None
            end_time = None
        elif not end_time:
            end_time = None

        if task_id.startswith('global_') and task_id in self.global_prayers:
            task = self.global_prayers[task_id]
            old_img = task.get('image_path')
            task['name'] = name
            task['start_time'] = start_time
            task['end_time'] = end_time
            task['image_path'] = image_path
            if repeat_days is not None:
                task['repeat_days'] = repeat_days
            if task['status'] == 'failed':
                task['status'] = 'pending'
            self.check_state_consistency(task, save=False)
            self.save_tasks()
            if old_img and old_img != image_path:
                self._schedule_cache_cleanup()
            return True
            
        for page in self.pages:
            for task in page['tasks']:
                if task['id'] == task_id:
                    old_img = task.get('image_path')
                    task['name'] = name
                    task['start_time'] = start_time
                    task['end_time'] = end_time
                    task['image_path'] = image_path
                    if repeat_days is not None:
                        task['repeat_days'] = repeat_days
                    if task['status'] == 'failed':
                        task['status'] = 'pending'
                    self.check_state_consistency(task, save=False)
                    self.save_tasks()
                    if old_img and old_img != image_path:
                        self._schedule_cache_cleanup()
                    return True
        return False

    def check_state_consistency(self, task, save=True):
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
                if save:
                    self.save_tasks()
                return 'disabled', True
            return 'disabled', False

        if now.weekday() not in repeat_days:
            if task.get('status') in ['active', 'failed']:
                task['status'] = 'pending'
                if save:
                    self.save_tasks()
                return 'pending', True
            return task.get('status', 'pending'), False

        current_status = task.get('status', 'pending')
        if current_status == 'done':
            return 'done', False

        start_str = task.get('start_time')
        end_str = task.get('end_time')
        now_secs = now.hour * 3600 + now.minute * 60 + now.second + (0.000001 if now.microsecond else 0.0)
        new_status = current_status

        # Case 1: Both Start & End OFF -> All-Day Active on scheduled days
        if not start_str:
            new_status = 'active'
        # Case 2: Start ON, End OFF -> Pending before start_time, Active afterwards (cannot fail)
        elif not end_str:
            try:
                start_secs = _parse_hhmm_to_secs(start_str)
            except (ValueError, KeyError):
                return current_status, False
            if now_secs < start_secs:
                new_status = 'pending'
            else:
                new_status = 'active'
        # Case 3: Both Start & End ON -> Full time window with deadline
        else:
            try:
                start_secs = _parse_hhmm_to_secs(start_str)
                end_secs = _parse_hhmm_to_secs(end_str)
            except (ValueError, KeyError):
                return current_status, False

            # Midnight Handling
            if end_secs < start_secs:
                if now.hour < 12:
                    start_secs -= 86400
                else:
                    end_secs += 86400

            if now_secs < start_secs:
                if current_status in ['active', 'failed', 'disabled']:
                    new_status = 'pending'
            elif start_secs <= now_secs <= end_secs:
                if current_status in ['pending', 'failed', 'disabled']:
                    new_status = 'active'
            elif now_secs > end_secs:
                if current_status in ['pending', 'active', 'disabled']:
                    new_status = 'failed'

        if new_status != current_status:
            task['status'] = new_status
            if save:
                self.save_tasks()
            return new_status, True

        return current_status, False

    def delete_task(self, task_id):
        task_id = str(task_id)
        if task_id.startswith('global_') and task_id in self.global_prayers:
            del self.global_prayers[task_id]
            self.save_tasks()
            self._schedule_cache_cleanup()
            return
            
        for page in self.pages:
            page['tasks'] = [t for t in page['tasks'] if str(t['id']) != task_id]
        self.save_tasks()
        self._schedule_cache_cleanup()


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

        changed = False
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
                existing = self.global_prayers[global_id]
                if (existing.get('start_time') != start_t or
                        existing.get('end_time') != end_t or
                        existing.get('image_path') != icon or
                        not existing.get('is_synced', False) or
                        not existing.get('enabled', False)):
                    changed = True
                existing.update({
                    'start_time': start_t,
                    'end_time': end_t,
                    'image_path': icon,
                    'is_synced': True,
                    'enabled': True
                })
            else:
                changed = True
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

        self.last_prayer_sync_changed = changed
        if changed:
            self.save_tasks()
        return True

    def remove_synced_tasks(self, page_id=None):
        """Hide/Disable synced tasks globally"""
        changed = False
        for t in self.global_prayers.values():
            if t.get('enabled', True):
                t['enabled'] = False
                changed = True
        if changed:
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
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        now_secs = now.hour * 3600 + now.minute * 60 + now.second + (0.000001 if now.microsecond else 0.0)
        now_hour = now.hour

        for task in self._iter_all_stored_tasks():
            # SAFETY: If completed TODAY, do not reset
            if task.get('status') == 'done':
                completed_at = task.get('completed_at')
                if completed_at and completed_at.startswith(today_str):
                    continue

            start_str = task.get('start_time')
            end_str = task.get('end_time')

            # Check overnight tasks only when both start and end times exist
            if start_str and end_str:
                try:
                    start_secs = _parse_hhmm_to_secs(start_str)
                    end_secs = _parse_hhmm_to_secs(end_str)

                    if end_secs < start_secs:
                        if now_hour < 12:
                            start_secs -= 86400
                        else:
                            end_secs += 86400

                    if start_secs <= now_secs <= end_secs and task['status'] == 'active':
                        continue
                except (ValueError, KeyError):
                    pass

            task['status'] = 'pending'
            task.pop('completed_at', None)
            self.check_state_consistency(task, save=False)

        self.save_tasks()

    def synchronize_task_statuses(self):
        """
        Synchronize all task statuses based on current time across ALL tasks.
        Returns (modified, changes) where changes is a list of
        (task_dict, old_status, new_status) tuples for every transition.
        """
        now = datetime.now()
        now_secs = now.hour * 3600 + now.minute * 60 + now.second + (0.000001 if now.microsecond else 0.0)
        now_hour = now.hour
        current_weekday = now.weekday()
        modified = False
        changes = []  # [(task, old_status, new_status), ...]

        for task in self._iter_all_stored_tasks():
            if not task.get('enabled', True):
                continue

            current_status = task.get('status', 'pending')

            if current_status == 'done':
                continue

            repeat_days = task.get('repeat_days', [0,1,2,3,4,5,6])

            if len(repeat_days) == 0:
                new_status = 'disabled'
            elif current_weekday not in repeat_days:
                new_status = 'pending'
            else:
                start_str = task.get('start_time')
                end_str = task.get('end_time')

                # Case 1: Both Start & End OFF -> All-Day Active
                if not start_str:
                    new_status = 'active'
                # Case 2: Start ON, End OFF -> Pending before start, Active afterwards (cannot fail)
                elif not end_str:
                    try:
                        start_secs = _parse_hhmm_to_secs(start_str)
                    except ValueError:
                        continue
                    if now_secs < start_secs:
                        new_status = 'pending'
                    else:
                        new_status = 'active'
                # Case 3: Both Start & End ON -> Full time window
                else:
                    try:
                        start_secs = _parse_hhmm_to_secs(start_str)
                        end_secs = _parse_hhmm_to_secs(end_str)
                    except ValueError:
                        continue

                    # Midnight handling: consistent with check_state_consistency
                    if end_secs < start_secs:
                        if now_hour < 12:
                            start_secs -= 86400
                        else:
                            end_secs += 86400

                    if start_secs <= now_secs <= end_secs:
                        new_status = 'active'
                    elif now_secs < start_secs:
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
                
            self.check_state_consistency(task, save=False)
            
        page['tasks'] = tasks
        self.save_tasks()
        return page
