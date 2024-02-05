from pymongo import MongoClient


class DB:
    def __init__(self):
        # Initialize MongoDB Atlas client and select database and collections
        self.client = MongoClient("mongodb://localhost:27017/")
        self.db = self.client["p2p-chat"]
        self.accounts = self.db["accounts"]

    def is_account_exist(self, username):
        # Check if an account with the given username exists
        return self.accounts.count_documents({"username": username}) > 0

    def register(self, username, password):
        # Register a new user account
        account = {"username": username, "password": password}
        self.accounts.insert_one(account)

    def get_password(self, username):
        # Retrieve the password for a given username
        user = self.accounts.find_one({"username": username})
        if user:
            return user["password"]
        else:
            return None