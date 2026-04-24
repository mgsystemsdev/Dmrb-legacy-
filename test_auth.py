from services.auth_service import authenticate
import os

os.environ["DATABASE_URL"] = "postgresql://miguelgonzalez@localhost:5432/dmrb_legacy"

res = authenticate("mga210", "Minato201")
if res:
    print("Authentication SUCCESSFUL")
    print(res)
else:
    print("Authentication FAILED")
