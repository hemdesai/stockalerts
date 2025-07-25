"""
Gmail configuration settings
"""
from pathlib import Path

# Gmail OAuth2 credentials filename
GMAIL_CREDENTIALS_FILENAME = "client_secret_376988780657-3a0kggkdph9og42hp0gv2r9ht9kgalni.apps.googleusercontent.com.json"

# Token filename (created after first authentication)
GMAIL_TOKEN_FILENAME = "token.json"

def get_credentials_path():
    """Get the full path to the Gmail credentials file"""
    from pathlib import Path
    credentials_dir = Path(__file__).parent.parent / 'credentials'
    return credentials_dir / GMAIL_CREDENTIALS_FILENAME

def get_token_path():
    """Get the full path to the Gmail token file"""
    from pathlib import Path
    credentials_dir = Path(__file__).parent.parent / 'credentials'
    return credentials_dir / GMAIL_TOKEN_FILENAME