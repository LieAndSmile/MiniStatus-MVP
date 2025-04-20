# app/utils/system_check.py
import shutil


def has_docker():
    return shutil.which("docker") is not None


def has_systemctl():
    return shutil.which("systemctl") is not None
