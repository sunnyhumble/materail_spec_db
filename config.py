import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据库配置
# 使用PostgreSQL（新服务器）
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'material_spec_db')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'material_spec')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '12345678')

# 数据库URL
DATABASE_URL = f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}'

# SQLite备用路径（仅在新服务器未配置时使用）
DATABASE_PATH = os.getenv('DATABASE_PATH', os.path.join(BASE_DIR, 'material_specs.db'))

SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')

API_KEY = os.getenv('OPENAI_API_KEY', 'sk-074b1fce0b6f4907944f8a621181884d')
API_BASE_URL = os.getenv('API_BASE_URL', 'https://api.openai.com/v1')
API_MODEL = os.getenv('API_MODEL', 'gpt-4o')
VISION_MODEL = os.getenv('VISION_MODEL', 'qwen-vl-max')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024
