
import struct
import base64
import zlib
import uuid
from .constants import ALL_ICONS

# Protocol Versions:
# V1: Legacy (Times + Icon + Name)
# V2: Adds Recurrence Days bitmask
# V3: Adds Page Name + None time sentinels (2047)
# V4: Ultra-compact variable-length bit-packed format (uncompressed, unpadded Base64)
# V5: Ultra-compact V4 payload compressed with raw Deflate (wbits=-15, unpadded Base64)
VERSION = 4
VERSION_COMPRESSED = 5

NONE_TIME_SENTINEL = 2047
DEFAULT_ICON = '📝'
ALL_DAYS_MASK = 0x7F


def _filter_shareable_tasks(tasks):
    """Filter out disabled-flag or globally synced prayer tasks."""
    return [
        t for t in tasks
        if t.get('enabled', True)
        and not t.get('is_synced', False)
        and not str(t.get('id', '')).startswith('global_')
    ]


def _encode_v4_body(valid_tasks, page_name=None):
    """
    Build the compact V4 binary body (excluding the outer version byte):
      - Header Byte: (page_mode << 6) | count_code
        * page_mode (2 bits):
          0 = None / empty
          1 = "Default"
          2 = "Routine"
          3 = Custom UTF-8 page name (1B length + UTF-8 bytes follow)
        * count_code (6 bits):
          0..62 = exact task count
          63    = extended count (1B count follows, up to 255)
      - Per-Task Record:
        * flags byte:
          - bits 0..2 (time_mode):
            0 = Both Start & End OFF (0 extra bytes)
            1 = Start ON (15-min multiple), End OFF (1B: sm // 15)
            2 = Start ON (exact minute), End OFF (2B: uint16 sm)
            3 = Both Start & End ON (both 15-min multiples) (2B: sm // 15, em // 15)
            4 = Both Start & End ON (exact minutes) (3B: 24-bit (sm << 12) | em)
          - bit 3 (custom_days):
            0 = All 7 days [0..6] (0 extra bytes)
            1 = Custom days bitmask (1B: 7-bit mask)
          - bit 4 (custom_icon):
            0 = Default icon '📝' (0 extra bytes)
            1 = Custom icon index in ALL_ICONS (1B: 0..255)
          - bits 5..7 (name_len_code):
            0..6 = Exact UTF-8 name byte length (0 extra length bytes)
            7    = Extended length (1B name_len follows)
    """
    body = bytearray()

    # Determine page_mode
    p_bytes = b''
    if not page_name:
        page_mode = 0
    elif page_name == "Default":
        page_mode = 1
    elif page_name == "Routine":
        page_mode = 2
    else:
        page_mode = 3
        p_bytes = page_name.encode('utf-8')[:255]

    count = len(valid_tasks)
    if count > 255:
        raise ValueError("Too many tasks to share (max 255)")

    count_code = count if count < 63 else 63
    body.append((page_mode << 6) | count_code)

    if page_mode == 3:
        body.append(len(p_bytes))
        body.extend(p_bytes)
    if count_code == 63:
        body.append(count)

    for task in valid_tasks:
        start_str = task.get('start_time')
        end_str = task.get('end_time') if start_str else None

        sm = _time_str_to_mins(start_str)
        em = _time_str_to_mins(end_str) if start_str else NONE_TIME_SENTINEL

        # 1. Time mode & time bytes
        time_bytes = bytearray()
        if sm >= 1440:
            time_mode = 0
        elif em >= 1440:
            if sm % 15 == 0:
                time_mode = 1
                time_bytes.append(sm // 15)
            else:
                time_mode = 2
                time_bytes.extend(struct.pack('>H', sm))
        else:
            if sm % 15 == 0 and em % 15 == 0:
                time_mode = 3
                time_bytes.append(sm // 15)
                time_bytes.append(em // 15)
            else:
                time_mode = 4
                packed_t = ((sm & 0xFFF) << 12) | (em & 0xFFF)
                time_bytes.append((packed_t >> 16) & 0xFF)
                time_bytes.append((packed_t >> 8) & 0xFF)
                time_bytes.append(packed_t & 0xFF)

        # 2. Recurrence days bitmask
        repeat_days = task.get('repeat_days', [0, 1, 2, 3, 4, 5, 6])
        mask = 0
        for d in repeat_days:
            if 0 <= d <= 6:
                mask |= (1 << d)
        custom_days = 0 if mask == ALL_DAYS_MASK else 1

        # 3. Icon
        icon_char = task.get('image_path', DEFAULT_ICON)
        if icon_char == DEFAULT_ICON or icon_char not in ALL_ICONS:
            custom_icon = 0
            icon_idx = 0
        else:
            idx_val = ALL_ICONS.index(icon_char)
            if idx_val <= 255:
                custom_icon = 1
                icon_idx = idx_val
            else:
                custom_icon = 0
                icon_idx = 0

        # 4. Name
        name_bytes = task.get('name', 'Task').encode('utf-8')[:255]
        n_len = len(name_bytes)
        name_len_code = n_len if n_len < 7 else 7

        flags = (
            (time_mode & 0x07)
            | ((custom_days & 0x01) << 3)
            | ((custom_icon & 0x01) << 4)
            | ((name_len_code & 0x07) << 5)
        )
        body.append(flags)
        body.extend(time_bytes)
        if custom_days:
            body.append(mask)
        if custom_icon:
            body.append(icon_idx)
        if name_len_code == 7:
            body.append(n_len)
        body.extend(name_bytes)

    return bytes(body)


def encode_tasks(tasks, page_name=None):
    """
    Encodes task list into an ultra-compact Share ID string (V4/V5).
    Automatically picks whichever representation (raw compact V4 or
    Deflate-compressed V5) produces the shorter Share ID, and strips
    redundant Base64 '=' padding.
    """
    valid_tasks = _filter_shareable_tasks(tasks)
    v4_body = _encode_v4_body(valid_tasks, page_name=page_name)

    # Try raw deflate (wbits=-15 omits the 2-byte zlib header & 4-byte checksum)
    compressor = zlib.compressobj(level=9, wbits=-15)
    deflated_body = compressor.compress(v4_body) + compressor.flush()

    if len(deflated_body) < len(v4_body):
        payload = bytes([VERSION_COMPRESSED]) + deflated_body
    else:
        payload = bytes([VERSION]) + v4_body

    return base64.urlsafe_b64encode(payload).decode('ascii').rstrip('=')


def _encode_tasks_v3(tasks, page_name=None):
    """
    Legacy V3 encoder retained for backward-compatibility testing and benchmarking.
    """
    buffer = bytearray()
    buffer.append(3)

    if page_name:
        page_bytes = page_name.encode('utf-8')[:255]
    else:
        page_bytes = b''
    buffer.append(len(page_bytes))
    buffer.extend(page_bytes)

    valid_tasks = _filter_shareable_tasks(tasks)
    count = len(valid_tasks)
    if count > 255:
        raise ValueError("Too many tasks to share (max 255)")
    buffer.append(count)

    for task in valid_tasks:
        start_str = task.get('start_time')
        end_str = task.get('end_time')

        sm = _time_str_to_mins(start_str)
        em = _time_str_to_mins(end_str) if start_str else NONE_TIME_SENTINEL

        icon_char = task.get('image_path', DEFAULT_ICON)
        try:
            icon_idx = ALL_ICONS.index(icon_char)
        except ValueError:
            icon_idx = 0

        sm = min(sm, 2047)
        em = min(em, 2047)
        icon_idx = min(icon_idx, 1023)

        packed_data = (sm << 21) | (em << 10) | icon_idx
        buffer.extend(struct.pack('>I', packed_data))

        repeat_days = task.get('repeat_days', [0, 1, 2, 3, 4, 5, 6])
        mask = 0
        for d in repeat_days:
            if 0 <= d <= 6:
                mask |= (1 << d)
        buffer.append(mask)

        name = task.get('name', 'Task').encode('utf-8')
        name_len = min(len(name), 255)
        buffer.append(name_len)
        buffer.extend(name[:name_len])

    return base64.urlsafe_b64encode(buffer).decode('ascii')


def decode_tasks(share_id):
    """
    Decodes a Share ID string back into (page_name, task_list).
    Fully supports:
      - Legacy V1, V2, and V3 codes (padded or unpadded Base64)
      - Compact V4 (uncompressed) and V5 (raw Deflate compressed) codes
    """
    try:
        if not share_id or not isinstance(share_id, str):
            return (None, [])

        cleaned = share_id.strip()
        if not cleaned:
            return (None, [])

        # Restore stripped '=' padding for Base64 decoding
        padded = cleaned + ('=' * (-len(cleaned) % 4))
        data = base64.urlsafe_b64decode(padded)

        if len(data) < 2:
            raise ValueError("Invalid ID length")

        ver = data[0]

        if ver in (1, 2, 3):
            return _decode_legacy_v1_v2_v3(data, ver)
        elif ver in (4, 5):
            return _decode_v4_v5(data, ver)
        else:
            raise ValueError(f"Unsupported version: {ver}")

    except Exception as e:
        print(f"Decode error: {e}")
        return (None, [])


def _decode_v4_v5(data, ver):
    """Decode V4 (uncompressed compact) or V5 (raw-deflated compact) payload."""
    if ver == VERSION_COMPRESSED:
        body = zlib.decompress(data[1:], -15)
    else:
        body = data[1:]

    if not body:
        raise ValueError("Empty V4/V5 body")

    idx = 0
    header = body[idx]
    idx += 1

    page_mode = (header >> 6) & 0x03
    count_code = header & 0x3F

    if page_mode == 0:
        page_name = None
    elif page_mode == 1:
        page_name = "Default"
    elif page_mode == 2:
        page_name = "Routine"
    else:
        p_len = body[idx]
        idx += 1
        page_name = body[idx:idx + p_len].decode('utf-8') if p_len > 0 else None
        idx += p_len

    if count_code == 63:
        count = body[idx]
        idx += 1
    else:
        count = count_code

    tasks = []
    for _ in range(count):
        if idx >= len(body):
            break

        flags = body[idx]
        idx += 1

        time_mode = flags & 0x07
        custom_days = (flags >> 3) & 0x01
        custom_icon = (flags >> 4) & 0x01
        name_len_code = (flags >> 5) & 0x07

        # 1. Decode Start & End Times
        if time_mode == 0:
            start_time = None
            end_time = None
        elif time_mode == 1:
            sm = body[idx] * 15
            idx += 1
            start_time = _mins_to_time_str(sm)
            end_time = None
        elif time_mode == 2:
            sm = struct.unpack('>H', body[idx:idx + 2])[0]
            idx += 2
            start_time = _mins_to_time_str(sm)
            end_time = None
        elif time_mode == 3:
            sm = body[idx] * 15
            em = body[idx + 1] * 15
            idx += 2
            start_time = _mins_to_time_str(sm)
            end_time = _mins_to_time_str(em) if start_time else None
        elif time_mode == 4:
            b0, b1, b2 = body[idx], body[idx + 1], body[idx + 2]
            idx += 3
            packed_t = (b0 << 16) | (b1 << 8) | b2
            sm = (packed_t >> 12) & 0xFFF
            em = packed_t & 0xFFF
            start_time = _mins_to_time_str(sm)
            end_time = _mins_to_time_str(em) if start_time else None
        else:
            raise ValueError(f"Invalid time_mode: {time_mode}")

        # 2. Decode Recurrence Days
        if custom_days == 0:
            repeat_days = [0, 1, 2, 3, 4, 5, 6]
        else:
            mask = body[idx]
            idx += 1
            repeat_days = [d for d in range(7) if (mask >> d) & 1]

        # 3. Decode Icon
        if custom_icon == 0:
            icon = DEFAULT_ICON
        else:
            icon_idx = body[idx]
            idx += 1
            icon = ALL_ICONS[icon_idx] if icon_idx < len(ALL_ICONS) else DEFAULT_ICON

        # 4. Decode Name
        if name_len_code < 7:
            n_len = name_len_code
        else:
            n_len = body[idx]
            idx += 1

        if idx + n_len > len(body):
            break
        name = body[idx:idx + n_len].decode('utf-8')
        idx += n_len

        tasks.append({
            'id': str(uuid.uuid4()),
            'name': name,
            'image_path': icon,
            'start_time': start_time,
            'end_time': end_time,
            'status': 'pending',
            'enabled': True,
            'repeat_days': repeat_days
        })

    return (page_name, tasks)


def _decode_legacy_v1_v2_v3(data, ver):
    """Decode legacy V1, V2, and V3 Share ID payloads without modification."""
    idx = 1

    page_name = None
    if ver >= 3:
        page_name_len = data[idx]
        idx += 1
        if page_name_len > 0:
            page_name = data[idx:idx + page_name_len].decode('utf-8')
            idx += page_name_len

    count = data[idx]
    idx += 1

    tasks = []
    for _ in range(count):
        min_needed = 5 if ver == 1 else 6
        if idx + min_needed > len(data):
            break

        packed_val = struct.unpack('>I', data[idx:idx + 4])[0]
        idx += 4

        start_mins = (packed_val >> 21) & 0x7FF
        end_mins = (packed_val >> 10) & 0x7FF
        icon_idx = packed_val & 0x3FF

        repeat_days = [0, 1, 2, 3, 4, 5, 6]
        if ver >= 2:
            mask = data[idx]
            idx += 1
            repeat_days = []
            for d in range(7):
                if (mask >> d) & 1:
                    repeat_days.append(d)

        name_len = data[idx]
        idx += 1

        if idx + name_len > len(data):
            break

        name_bytes = data[idx:idx + name_len]
        name = name_bytes.decode('utf-8')
        idx += name_len

        icon = ALL_ICONS[icon_idx] if icon_idx < len(ALL_ICONS) else DEFAULT_ICON
        start_time = _mins_to_time_str(start_mins)
        end_time = _mins_to_time_str(end_mins) if start_time else None

        tasks.append({
            'id': str(uuid.uuid4()),
            'name': name,
            'image_path': icon,
            'start_time': start_time,
            'end_time': end_time,
            'status': 'pending',
            'enabled': True,
            'repeat_days': repeat_days
        })

    return (page_name, tasks)


def _time_str_to_mins(t_str):
    if not t_str:
        return NONE_TIME_SENTINEL
    try:
        h, m = map(int, t_str.split(':'))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h * 60 + m
        return NONE_TIME_SENTINEL
    except Exception:
        return NONE_TIME_SENTINEL


def _mins_to_time_str(mins):
    if mins >= 1440:
        return None
    h = (mins // 60) % 24
    m = mins % 60
    return f"{h:02d}:{m:02d}"

