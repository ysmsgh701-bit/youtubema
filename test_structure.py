"""Pipeline v2 structure validation test"""
import sys
import os
sys.path.insert(0, ".")
os.environ["PYTHONIOENCODING"] = "utf-8"

print("=" * 50)
print("  YouTube Pipeline v2 - Structure Test")
print("=" * 50)

# 1. Config
try:
    from config import CHANNELS, VIDEO_FORMATS, CHARACTER_PROMPT
    print("\n[OK] config.py loaded")
    for k, v in CHANNELS.items():
        print(f"    Channel: {k} -> {v['name']} (TTS: {v['tts_lang']})")
    for k, v in VIDEO_FORMATS.items():
        print(f"    Format: {k} -> {v['width']}x{v['height']} @ {v['fps']}fps")
except Exception as e:
    print(f"[FAIL] config.py: {e}")

# 2. Module imports
modules = [
    ("scripts.script_translator", "generate_all_translations"),
    ("scripts.audio_gen", "generate_audio_from_script"),
    ("scripts.video_render", "render_video"),
    ("scripts.thumbnail_gen", "generate_thumbnails"),
    ("scripts.youtube_upload", "upload_video"),
]

for mod_name, func_name in modules:
    try:
        mod = __import__(mod_name, fromlist=[func_name])
        fn = getattr(mod, func_name)
        print(f"[OK] {mod_name}.{func_name}")
    except Exception as e:
        print(f"[FAIL] {mod_name}: {e}")

# 3. main_macro
try:
    from main_macro import YouTubeAutomationPipelineV2
    print(f"[OK] main_macro.YouTubeAutomationPipelineV2")
except Exception as e:
    print(f"[FAIL] main_macro: {e}")

print("\n" + "=" * 50)
print("  Validation Complete!")
print("=" * 50)
