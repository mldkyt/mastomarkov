
import logging
import os


def get_logger(name: str) -> logging.Logger:
    if not os.path.exists("logs"):
        os.mkdir("logs")

    mkmarkov_logger = logging.getLogger(name)
    mkmarkov_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    mkmarkov_logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(
        filename=f"logs/{name}.log", mode="a", encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(mkmarkov_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(mkmarkov_formatter)

    mkmarkov_logger.addHandler(file_handler)
    mkmarkov_logger.addHandler(console_handler)

    return mkmarkov_logger

