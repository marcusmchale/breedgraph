import logging

def pytest_configure(config):
    logging.getLogger("faker.factory").setLevel(logging.CRITICAL)