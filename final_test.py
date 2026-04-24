from services.auth_service import hash_password, verify_password
from db.repository import user_repository
import os

os.environ["DATABASE_URL"] = "postgresql://localhost/dmrb_legacy"

username = "mga210"
password = "Minato201"

user = user_repository.get_active_by_username(username)
if not user:
    print("User not found")
    exit(1)

ph = hash_password(password)
user_repository.update_password_hash(user["user_id"], ph)

# Fetch again to verify
user_updated = user_repository.get_active_by_username(username)
match = verify_password(user_updated["password_hash"], password)

print(f"Update successful: {match}")
print(f"Hash: {user_updated['password_hash']}")
