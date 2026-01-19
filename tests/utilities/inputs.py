import logging

import bcrypt

from faker import Faker

from src.breedgraph.config import MAIL_USERNAME, MAIL_HOST
import traceback
logger = logging.getLogger(__name__)

class UserInputGenerator:
    def __init__(self):
        #Faker.seed(7)
        # https://faker.readthedocs.io/en/master/locales.html
        self.fake = Faker(['fr_FR', 'es_ES', 'zh_CN'])
        self.user_inputs = list()

    def new_user_input(self):
        name = self.fake.unique.name()
        email_suffix = self.fake.ascii_safe_email()[0:-12]
        # mailhog only supports ascii
        password = self.fake.password()
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        company = self.fake.company()

        user_input = {
            "name": name,
            "email": f"{MAIL_USERNAME}+_test_user_{email_suffix}@{MAIL_HOST}",
            "password": password,
            "password_hash": password_hash,
            "team_name": company
        }
        self.user_inputs.append(user_input)
        return user_input


class LoremTextGenerator:
    def __init__(self):
        #Faker.seed(7)
        # https://faker.readthedocs.io/en/master/locales.html
        self.fake = Faker(['fr_FR', 'es_ES', 'zh_CN'])
        self.inputs = list()

    def new_text(self, max_nb_chars=50):
        text = self.fake.text(max_nb_chars=max_nb_chars)
        self.inputs.append(text)
        return text