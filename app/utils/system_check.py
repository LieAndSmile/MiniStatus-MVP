# app/utils/system_check.py
import shutil


def has_systemctl():
    return shutil.which("systemctl") is not None
