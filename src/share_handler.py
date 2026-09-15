
import struct
import base64
import zlib
from .constants import ALL_ICONS

# Protocol Version 3 (Adds Page Name)
VERSION = 3

def encode_tasks(tasks, page_name=None):
    """
    Encodes task list into a compressed Share ID string.
    V3 Format: [Version:1][PageNameLen:1][PageName:N][Count:1][(Start|End|Icon):4][Days:1][NameLen:1][Name:N]...
    
    Times are packed into minutes from midnight (max 1440).
    Start (11 bits) | End (11 bits) | IconIndex (10 bits) = 32 bits (4 bytes).
    + Days (1 byte/8 bits) = Bitmask 0-6
    """
    buffer = bytearray()
    
    # Header: Version (1 byte)
    buffer.append(VERSION)
    
    # NEW (V3): Page Name (length-prefixed UTF-8)
    if page_name:
        page_bytes = page_name.encode('utf-8')[:255]
    else:
        page_bytes = b''
    buffer.append(len(page_bytes))
    buffer.extend(page_bytes)
    
    # Task Count (1 byte)
    valid_tasks = [t for t in tasks if t.get('enabled', True) and not t.get('is_synced') and not str(t.get('id', '')).startswith('global_') and t.get('name') not in ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']]
    count = len(valid_tasks)
    if count > 255:
        raise ValueError("Too many tasks to share (max 255)")
    buffer.append(count)
    
    for task in valid_tasks:
        # 1. Parse Times -> Minutes
        start_str = task.get('start_time', '00:00')
        end_str = task.get('end_time', '23:59')
        
        sm = _time_str_to_mins(start_str)
        em = _time_str_to_mins(end_str)
        
        # 2. Icon Index
        icon_char = task.get('image_path', '📝')
        try:
            icon_idx = ALL_ICONS.index(icon_char)
        except ValueError:
            icon_idx = 0
            
        # 3. Bit Packing (Times + Icon)
        sm = min(sm, 2047)
        em = min(em, 2047)
        icon_idx = min(icon_idx, 1023)
        
        packed_data = (sm << 21) | (em << 10) | icon_idx
        buffer.extend(struct.pack('>I', packed_data))
        
        # 4. Recurrence Days Bitmask
        repeat_days = task.get('repeat_days', [0,1,2,3,4,5,6])
        mask = 0
        for d in repeat_days:
            if 0 <= d <= 6:
                mask |= (1 << d)
        buffer.append(mask)
        
        # 5. Name
        name = task.get('name', 'Task').encode('utf-8')
        name_len = min(len(name), 255)
        buffer.append(name_len)
        buffer.extend(name[:name_len])
        
    # Compress and Base64
    return base64.urlsafe_b64encode(buffer).decode('ascii')

def decode_tasks(share_id):
    """
    Decodes Share ID string back into (page_name, task_list).
    Returns tuple: (page_name_or_None, list_of_dicts)
    Backward compatible with V1/V2.
    """
    try:
        data = base64.urlsafe_b64decode(share_id)
        
        idx = 0
        
        if len(data) < 2:
            raise ValueError("Invalid ID length")
            
        ver = data[idx]
        idx += 1
        
        if ver not in [1, 2, 3]:
            raise ValueError(f"Unsupported version: {ver}")
        
        # V3: Page Name
        page_name = None
        if ver >= 3:
            page_name_len = data[idx]
            idx += 1
            if page_name_len > 0:
                page_name = data[idx:idx+page_name_len].decode('utf-8')
                idx += page_name_len
            
        count = data[idx]
        idx += 1
        
        tasks = []
        
        import uuid
        
        for _ in range(count):
            min_needed = 5 if ver == 1 else 6
            if idx + min_needed > len(data): 
                break
                
            # Unpack 4 bytes (Times + Icon)
            packed_val = struct.unpack('>I', data[idx:idx+4])[0]
            idx += 4
            
            # Extract fields
            start_mins = (packed_val >> 21) & 0x7FF
            end_mins = (packed_val >> 10) & 0x7FF
            icon_idx = packed_val & 0x3FF
            
            # Recurrence Days
            repeat_days = [0,1,2,3,4,5,6]
            if ver >= 2:
                mask = data[idx]
                idx += 1
                repeat_days = []
                for d in range(7):
                    if (mask >> d) & 1:
                        repeat_days.append(d)
            
            # Name
            name_len = data[idx]
            idx += 1
            
            if idx + name_len > len(data):
                break
                
            name_bytes = data[idx:idx+name_len]
            name = name_bytes.decode('utf-8')
            idx += name_len
            
            # Reconstruct Task
            icon = ALL_ICONS[icon_idx] if icon_idx < len(ALL_ICONS) else '📝'
            
            tasks.append({
                'id': str(uuid.uuid4()),
                'name': name,
                'image_path': icon, 
                'start_time': _mins_to_time_str(start_mins),
                'end_time': _mins_to_time_str(end_mins),
                'status': 'pending',
                'enabled': True,
                'repeat_days': repeat_days
            })
            
        return (page_name, tasks)
        
    except Exception as e:
        print(f"Decode error: {e}")
        return (None, [])

def _time_str_to_mins(t_str):
    try:
        h, m = map(int, t_str.split(':'))
        return h * 60 + m
    except:
        return 0

def _mins_to_time_str(mins):
    h = (mins // 60) % 24
    m = mins % 60
    return f"{h:02d}:{m:02d}"
