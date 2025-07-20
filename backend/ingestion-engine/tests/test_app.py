import logging

from src import app


def do_something(x):
    logging.info("Starting do_something")
    return x + 1


def test_do_something():
    assert do_something(1) == 2


def test_main_runs():
    assert hasattr(app, "main")
