import hashlib

from src.domain.interfaces.hash_creator_interface import HashCreatorInterface


class HashCreator(HashCreatorInterface):
    async def create_hash(self, password):
        sha256hash = hashlib.sha256()
        sha256hash.update(password.encode('utf-8'))
        return str(sha256hash.hexdigest())