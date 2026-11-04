"""بررسی فقط‌خواندنی حساب؛ هیچ منبع ابری ایجاد نمی‌کند."""

import json
import shutil
import subprocess

aws = shutil.which("aws")
if not aws:
    raise SystemExit("ابتدا ابزار خط فرمان AWS و نمایهٔ حساب آزمایشی را تنظیم کنید.")

commands = {
    "هویت حساب": ["sts", "get-caller-identity"],
    "طرح و اعتبار Free Tier": [
        "freetier",
        "get-account-plan-state",
        "--region",
        "us-east-1",
    ],
    "مصرف Free Tier": ["freetier", "get-free-tier-usage", "--region", "us-east-1"],
    "بودجه‌های موجود": None,
}
account = None
failed = False
for label, command in commands.items():
    if command is None:
        if not account:
            continue
        command = ["budgets", "describe-budgets", "--account-id", account]
    result = subprocess.run(
        [aws, *command, "--output", "json", "--no-cli-pager"],
        capture_output=True,
        text=True,
    )
    print(f"\n{label}:")
    if result.returncode:
        failed = True
        print(
            "نتیجه در دسترس نیست؛ دسترسی حساب، نسخهٔ ابزار و صفحهٔ صورتحساب را بررسی کنید."
        )
        continue
    payload = json.loads(result.stdout)
    if label == "هویت حساب":
        account = payload["Account"]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
print("\nپیش از ایجاد منبع، اعتبار، منطقه، قیمت و دسترسی سرویس را در کنسول تأیید کنید.")
if failed:
    raise SystemExit(1)
