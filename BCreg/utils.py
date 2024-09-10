import os
from urllib.parse import urlencode

def load_config():
    """
    Loads database configuration from environment variables.

    Returns:
        dict: A dictionary containing database configuration.

    Raises:
        KeyError: If a required environment variable is missing.
    """
    # Load configuration from environment variables with defaults
    config = {
        'host': os.environ.get('DB_HOST', 'hoghidan1.mysql.pythonanywhere-services.com'),
        'user': os.environ.get('DB_USER', 'hoghidan1'),  # Note potential typo
        'password': os.environ.get('DB_PASSWORD', 'english92'),
        'database': os.environ.get('DB_NAME', 'hoghidan1$default'),
        'port': os.environ.get('DB_PORT', 3306)  # Default to 3306 for MySQL
    }

    # Validate required environment variables
    for key, value in config.items():
        if value is None:
            raise KeyError(f"Missing required environment variable: {key}")

    return config

def generate_db_uri():
    """
    Generates the database connection URI from environment variables.

    Returns:
        str: The constructed database connection URI.

    Raises:
        KeyError: If a required environment variable is missing.
    """
    config = load_config()
    
    # Create connection URI with URL encoding for special characters
    params = urlencode({
        'charset': 'utf8'  # Optional: include charset for clarity
    })
    
    # Construct the database URI
    db_uri = (
        f"mysql+pymysql://{config['user']}:{config['password']}@"
        f"{config['host']}:{config['port']}/{config['database']}?{params}"
    )

    return db_uri

# Example usage:
try:
    db_uri = generate_db_uri()
    print(db_uri)
except KeyError as e:
    print(f"Error: {e}")

# install PyMySQL 
# #generate database connect URI
# def generate_db_uri() -> str:
#     config = load_config()['DB']
#     return f"mysql+pymysql://{config['hoghidan1']}:{config['english92']}@{config['hoghidan1.mysql.pythonanywhere-services.com']}:{config['3306']}/{config['users']}"
 
