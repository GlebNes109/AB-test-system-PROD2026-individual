import hashlib



class HashCreator:
    async def create_hash(self, password):
        sha256hash = hashlib.sha256()
        sha256hash.update(password.encode('utf-8'))
        return str(sha256hash.hexdigest())