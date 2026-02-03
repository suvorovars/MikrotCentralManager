def encrypt_password(password: str) -> str:
    if password:
        return password[::-1]
    else:
        return ""

def decrypt_password(password: str) -> str:
    if password:
        return password[::-1]
    else:
        return ""
