"""
Password hashing and verification utilities using bcrypt.
"""
import bcrypt
import os


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Hashed password string (bcrypt format)
    """
    # Generate a salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hashed password.
    Supports both bcrypt hashes and plain text (for backward compatibility).
    
    Args:
        password: Plain text password to verify
        hashed_password: Hashed password (bcrypt format) or plain text (legacy)
        
    Returns:
        True if password matches, False otherwise
    """
    # Check if the stored password is already a bcrypt hash
    # Bcrypt hashes start with $2a$, $2b$, or $2y$ followed by cost and salt
    if hashed_password.startswith('$2'):
        # It's a bcrypt hash, verify normally
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception:
            return False
    else:
        # Legacy plain text password - compare directly for backward compatibility
        # This allows existing installations to continue working
        return password == hashed_password


def is_password_hashed(password: str) -> bool:
    """
    Check if a password string is already hashed.
    
    Args:
        password: Password string to check
        
    Returns:
        True if the password appears to be a bcrypt hash, False otherwise
    """
    return password.startswith('$2')


def migrate_password_in_env(env_path: str) -> bool:
    """
    Migrate plain text password to hashed password in .env file.
    This function reads the .env file, checks if ADMIN_PASSWORD is plain text,
    and if so, hashes it and updates the file.
    
    Args:
        env_path: Path to the .env file
        
    Returns:
        True if migration was performed, False if already hashed or not found
    """
    if not os.path.exists(env_path):
        return False
    
    # Read the .env file
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Find and update ADMIN_PASSWORD line
    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith('ADMIN_PASSWORD='):
            # Extract the password value
            password_value = line.split('=', 1)[1].strip()
            # Remove quotes if present
            if password_value.startswith('"') and password_value.endswith('"'):
                password_value = password_value[1:-1]
            elif password_value.startswith("'") and password_value.endswith("'"):
                password_value = password_value[1:-1]
            
            # Check if it's already hashed
            if not is_password_hashed(password_value):
                # Hash the password
                hashed = hash_password(password_value)
                new_lines.append(f'ADMIN_PASSWORD={hashed}\n')
                updated = True
            else:
                # Already hashed, keep as is
                new_lines.append(line)
        else:
            new_lines.append(line)
    
    # Write back if updated
    if updated:
        with open(env_path, 'w') as f:
            f.writelines(new_lines)
        return True
    
    return False


def update_password_in_env(env_path: str, new_password: str) -> bool:
    """
    Update the ADMIN_PASSWORD in .env file with a new hashed password.
    
    Args:
        env_path: Path to the .env file
        new_password: New plain text password to set (will be hashed)
        
    Returns:
        True if password was updated successfully, False otherwise
    """
    if not os.path.exists(env_path):
        return False
    
    # Hash the new password
    hashed_password = hash_password(new_password)
    
    # Read the .env file
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Find and update ADMIN_PASSWORD line
    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith('ADMIN_PASSWORD='):
            new_lines.append(f'ADMIN_PASSWORD={hashed_password}\n')
            updated = True
        else:
            new_lines.append(line)
    
    # Write back if updated
    if updated:
        with open(env_path, 'w') as f:
            f.writelines(new_lines)
        return True
    
    return False

