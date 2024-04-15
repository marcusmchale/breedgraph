import bcrypt

from faker import Faker

from src.breedgraph.config import MAIL_USERNAME, MAIL_HOST

class UserInputGenerator:
    def __init__(self):
        self.fake = Faker('fr_Fr')
        #self.fake = Faker('zh_CN')
        self.user_inputs = list()

    def new_user_input(self):
        password = self.fake.password()
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        user_input = {
            "name": self.fake.unique.name(),
            "email": f"{MAIL_USERNAME}+_test_user_{len(self.user_inputs)+1}@{MAIL_HOST}",
            "password": password,
            "password_hash": password_hash,
            "team_name": self.fake.company()
        }
        self.user_inputs.append(user_input)
        return user_input
