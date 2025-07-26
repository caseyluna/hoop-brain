import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseJob(ABC):
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    @abstractmethod
    def run(self):
        pass

    def log(self, msg: str):
        logger.info(f"[{self.__class__.__name__}] {msg}")
