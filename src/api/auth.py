import os

class Auth:
    def __init__(self) -> None:
        self.internal_api_key = os.getenv("INTERNAL_API_KEY")

    def set_internal_api_key(self, key):
        self.internal_api_key = key

    def validate_credentials(self, key):
        return key == self.internal_api_key