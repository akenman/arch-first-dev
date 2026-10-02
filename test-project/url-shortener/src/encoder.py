import re
import secrets
import string


BASE62_ALPHABET = string.ascii_letters + string.digits


class URLEncoder:
    def __init__(self, code_length: int = 6):
        self.code_length = code_length

    def encode(self, long_url: str) -> str:
        if not self._is_valid_url(long_url):
            raise ValueError(f"Invalid URL: {long_url}")

        return ''.join(secrets.choice(BASE62_ALPHABET) for _ in range(self.code_length))

    def is_valid_code(self, short_code: str) -> bool:
        pattern = re.compile(rf'^[a-zA-Z0-9]{{{self.code_length},{self.code_length + 2}}}$')
        return bool(pattern.match(short_code))

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return bool(pattern.match(url))
