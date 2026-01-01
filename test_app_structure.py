#!/usr/bin/env python3
"""
Simple test script to verify the app structure after Docker removal.
This checks that all imports work and no Docker-related code remains.
"""

import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_no_docker_references():
    """Check that no Docker-related code remains"""
    docker_keywords = [
        'sync_docker',
        'get_docker_container_ports',
        'has_docker',
        'interpret_docker_status',
        '.sync_docker(',
        'docker ps',
        'docker.sock'
    ]
    
    issues = []
    for root, dirs, files in os.walk('app'):
        # Skip __pycache__
        if '__pycache__' in dirs:
            dirs.remove('__pycache__')
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r') as f:
                        content = f.read()
                    
                    for keyword in docker_keywords:
                        if keyword in content:
                            issues.append(f'{filepath}: contains "{keyword}"')
                except Exception as e:
                    issues.append(f'{filepath}: error reading - {e}')
    
    return issues

def check_imports():
    """Check that all imports can be resolved"""
    print("Testing imports...")
    
    try:
        # Test core imports
        from app.extensions import db
        print("✓ app.extensions.db imported")
        
        from app.models import Service, Tag
        print("✓ app.models imported")
        
        from app.utils.system_check import has_systemctl
        print("✓ app.utils.system_check imported")
        
        # Verify has_docker doesn't exist
        try:
            from app.utils.system_check import has_docker
            print("❌ has_docker still exists!")
            return False
        except ImportError:
            print("✓ has_docker correctly removed")
        
        from app.utils.auto_tag import auto_assign_tags
        print("✓ app.utils.auto_tag imported")
        
        from app.services.sync_service import ServiceSync
        print("✓ app.services.sync_service imported")
        
        # Verify sync_docker doesn't exist
        if hasattr(ServiceSync, 'sync_docker'):
            print("❌ ServiceSync.sync_docker still exists!")
            return False
        else:
            print("✓ ServiceSync.sync_docker correctly removed")
        
        # Verify sync_systemd and sync_ports still exist
        assert hasattr(ServiceSync, 'sync_systemd'), "sync_systemd missing!"
        assert hasattr(ServiceSync, 'sync_ports'), "sync_ports missing!"
        assert hasattr(ServiceSync, 'sync_all'), "sync_all missing!"
        print("✓ Required sync methods exist")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"⚠️  Unexpected error: {e}")
        return False

def main():
    print("=" * 60)
    print("Testing MiniStatus-MVP Application Structure")
    print("=" * 60)
    print()
    
    # Check for Docker references
    print("1. Checking for Docker references...")
    docker_issues = check_no_docker_references()
    if docker_issues:
        print("❌ Found Docker references:")
        for issue in docker_issues:
            print(f"   {issue}")
        return False
    else:
        print("✓ No Docker references found")
    
    print()
    
    # Check imports (only if Flask is available)
    try:
        import flask
        print("2. Flask is available, testing imports...")
        if not check_imports():
            return False
    except ImportError:
        print("2. Flask not installed, skipping import tests")
        print("   (This is OK for structure verification)")
    
    print()
    print("=" * 60)
    print("✅ All tests passed! Application structure is correct.")
    print("=" * 60)
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

