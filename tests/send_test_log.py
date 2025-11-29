# tests/send_test_log.py
import sys
from pathlib import Path

# Add project root to Python path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from log_to_supabase import log_event

def main():
    log_event("info", "test log from script", {"test": True})
    print("Sent log (fire-and-forget). Check Supabase table.")

if __name__ == "__main__":
    main()

