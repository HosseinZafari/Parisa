"""پشتیبان سازگار SQLite؛ داخل کانتینر اجرا شود، نه با کپی فایل WAL فعال."""

import argparse
import sqlite3
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("destination", type=Path)
args = parser.parse_args()
if args.destination.exists():
    parser.error("پروندهٔ مقصد وجود دارد؛ نام تازه‌ای انتخاب کنید.")
with (
    sqlite3.connect("/app/backend/data/parisa.db") as source,
    sqlite3.connect(args.destination) as target,
):
    source.backup(target)
print("پشتیبان پایگاه داده ساخته شد.")
