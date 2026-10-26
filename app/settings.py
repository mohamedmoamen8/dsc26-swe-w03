# -*- coding: utf-8 -*-
import time
from dataclasses import dataclass


@dataclass
class Settings:
    database_url: str = "sqlite:///./rawaj.db"
    api_tokens: dict = None
    rate_limit_capacity: int = 5
    rate_limit_refill_per_second: float = 1.0
    max_transfer_piastres: int = 2_000_000
    clock = time.monotonic

    def __post_init__(self):
        if self.api_tokens is None:
            self.api_tokens = {}
