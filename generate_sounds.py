import os
import math
import struct
import wave
import random

def generate_wave(frequency, duration, volume=0.5, sample_rate=44100, wave_type='sine', envelope='pluck'):
    n_samples = int(sample_rate * duration)
    data = []
    
    # ADSR Envelope parameters
    if envelope == 'pluck':
        # Fast attack, long exponential decay (Glassy/Pluck)
        attack_len = int(n_samples * 0.05)
        decay_len = n_samples - attack_len
    elif envelope == 'pad':
        # Slow attack, sustain, slow release (Soft/Pad)
        attack_len = int(n_samples * 0.3)
        decay_len = int(n_samples * 0.3)
    else: # percussive
        attack_len = int(n_samples * 0.01)
        decay_len = n_samples - attack_len

    for i in range(n_samples):
        t = i / sample_rate
        
        # 1. Base Waveform
        val = 0.0
        if wave_type == 'sine':
            val = math.sin(2.0 * math.pi * frequency * t)
            # Add subtle harmonics for richness (Electric Piano ish)
            val += 0.5 * math.sin(2.0 * math.pi * (frequency * 2) * t)
            val += 0.25 * math.sin(2.0 * math.pi * (frequency * 3) * t)
            val /= 1.75 # Normalize
        elif wave_type == 'triangle':
            # Smoother than square
            phase = (frequency * t) % 1.0
            val = 4.0 * abs(phase - 0.5) - 1.0
            
        # 2. Apply Envelope (Volume Shaping)
        env = 1.0
        if i < attack_len:
            env = i / attack_len
        elif envelope == 'pluck':
            # Exponential decay
            rel_i = i - attack_len
            env = math.exp(-3.0 * rel_i / decay_len) 
        elif envelope == 'pad':
            if i > n_samples - decay_len:
                 rel_i = i - (n_samples - decay_len)
                 env = 1.0 - (rel_i / decay_len)
        
        # 3. Final Value
        sample = int(val * env * volume * 32767.0)
        data.append(struct.pack('<h', max(-32767, min(32767, sample))))
        
    return b''.join(data)

def mix_tracks(track1, track2):
    # Determine max length
    len1 = len(track1)
    len2 = len(track2)
    max_len = max(len1, len2)
    
    # Pad with zeros
    t1 = track1 + b'\x00' * (max_len - len1)
    t2 = track2 + b'\x00' * (max_len - len2)
    
    mixed = []
    # Process 2 bytes at a time (16-bit)
    for i in range(0, max_len, 2):
        try:
            val1 = struct.unpack('<h', t1[i:i+2])[0]
            val2 = struct.unpack('<h', t2[i:i+2])[0]
            mixed_val = int((val1 + val2) * 0.8) # Mix and prevent clipping
            mixed.append(struct.pack('<h', max(-32767, min(32767, mixed_val))))
        except: pass
        
    return b''.join(mixed)

def generate_sound_assets(base_dir):
    sounds_dir = os.path.join(base_dir, "assets", "sounds")
    os.makedirs(sounds_dir, exist_ok=True)
    
    print(f"Generating Modern Sounds in {sounds_dir}...")

    # 1. Start (Smooth, modern warm 2-step rising marimba/Rhodes cue for task start & daily reset)
    # Distinct from the bright high-register 'done.wav' completion chime:
    # Warm low-mid F4 (349.23 Hz) -> A4 (440.00 Hz) with soft fifth/octave warmth and stereo width.
    sr = 44100
    dur = 0.68
    n_frames = int(sr * dur)
    stereo_frames = bytearray(n_frames * 4)

    notes = [
        # (start_sec, freq_fundamental, freq_warm_harmonic, amp, decay_rate, pan_l, pan_r)
        (0.000, 349.23, 523.25, 0.28, 6.2, 0.96, 0.88),  # Warm F4 + soft C5 fifth
        (0.115, 440.00, 698.46, 0.34, 4.8, 0.88, 0.96),  # Smooth rising A4 + soft F5 octave-sixth
    ]

    for i in range(n_frames):
        t = i / sr
        left = 0.0
        right = 0.0
        for t0, f1, f2, amp, decay, pl, pr in notes:
            dt = t - t0
            if dt <= 0.0:
                continue
            # Smooth 14ms raised-cosine attack (zero click, warm felt mallet feel)
            if dt < 0.014:
                attack = 0.5 * (1.0 - math.cos(math.pi * dt / 0.014))
            else:
                attack = 1.0
            env = attack * math.exp(-decay * dt)
            # Fundamental + soft rapidly-decaying warm overtone (Rhodes/marimba timbre)
            overtone_env = math.exp(-decay * 2.1 * dt)
            sig_l = (
                math.sin(2.0 * math.pi * f1 * dt)
                + 0.26 * overtone_env * math.sin(2.0 * math.pi * f2 * dt)
                + 0.10 * overtone_env * math.sin(2.0 * math.pi * (f1 * 2.0) * dt)
            )
            sig_r = (
                math.sin(2.0 * math.pi * (f1 * 1.0008) * dt + 0.12)
                + 0.26 * overtone_env * math.sin(2.0 * math.pi * (f2 * 0.9994) * dt + 0.20)
                + 0.10 * overtone_env * math.sin(2.0 * math.pi * (f1 * 2.0) * dt)
            )
            left += sig_l * env * amp * pl
            right += sig_r * env * amp * pr

        # Smooth tail fade-out over final 45ms
        if t > dur - 0.045:
            tail = max(0.0, (dur - t) / 0.045)
            left *= tail
            right *= tail

        sl = max(-32767, min(32767, int(left * 32767.0)))
        sr_val = max(-32767, min(32767, int(right * 32767.0)))
        struct.pack_into('<hh', stereo_frames, i * 4, sl, sr_val)

    with wave.open(os.path.join(sounds_dir, "start.wav"), 'w') as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(stereo_frames)

    # 2. Done (Crisp "pop" + high shimmer) -> Modern "Complete"
    # High Sine E6 (1318) short
    pop = generate_wave(1318.51, 0.3, 0.5, envelope='pluck')
    # Lower harmonic cue C6
    base = generate_wave(1046.50, 0.4, 0.3, envelope='pluck')
    done_mix = mix_tracks(base, pop)
    
    with wave.open(os.path.join(sounds_dir, "done.wav"), 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(done_mix)

    # 3. Fail (Soft low "Thud" or "Bonk") -> Not harsh
    # Low Triangle Wave roughly F3
    fail_tone = generate_wave(174.61, 0.4, 0.6, wave_type='triangle', envelope='pluck')
    
    with wave.open(os.path.join(sounds_dir, "fail.wav"), 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(fail_tone)

    # 4. Urgent (Soft Radar Pulse) -> Non-stressful alert
    # Two pulses of sine wave
    pulse = generate_wave(880.00, 0.15, 0.4, envelope='pad') # Soft attack/decay
    silence = b'\x00' * int(44100 * 0.1 * 2)
    urgent_mix = pulse + silence + pulse
    
    with wave.open(os.path.join(sounds_dir, "urgent.wav"), 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(urgent_mix)
        
    # 5. Reminder (Water Drop / Woodblock)
    # High frequency short sine with pitch bend simulation (manual freq shifting is hard in this loop, so standard short pluck)
    # 2000Hz very short
    drop = generate_wave(2000, 0.05, 0.3, envelope='pluck')
    
    with wave.open(os.path.join(sounds_dir, "reminder.wav"), 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(drop)

if __name__ == "__main__":
    generate_sound_assets("D:\\Programs\\Windsurf\\Projects\\Daily Tasks")
