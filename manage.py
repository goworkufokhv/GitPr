import os
import sys
from pathlib import Path

def main():
    """Run administrative tasks."""
     # ✅ 루트 경로를 sys.path에 추가해서 Python이 앱을 확실히 찾도록 보정
    BASE_DIR = Path(__file__).resolve().parent
    sys.path.append(str(BASE_DIR))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lotto_site.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()

