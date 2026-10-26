# -*- coding: utf-8 -*-
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False}, pool_pre_ping=True)
    return create_engine(url, pool_pre_ping=True)


def make_session_factory(engine: Engine):
    from sqlalchemy.orm import sessionmaker
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
