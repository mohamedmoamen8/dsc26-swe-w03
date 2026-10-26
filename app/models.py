# -*- coding: utf-8 -*-
import uuid

from sqlalchemy import Column, ForeignKey, Integer, String, CheckConstraint
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True)
    customer_id = Column(String, nullable=False)
    balance_piastres = Column(Integer, nullable=False)

    __table_args__ = (CheckConstraint("balance_piastres >= 0", name="ck_accounts_balance_non_negative"),)


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(String, primary_key=True)
    from_account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    to_account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    amount_piastres = Column(Integer, nullable=False)
    memo = Column(String(140), nullable=True)
    status = Column(String, nullable=False, default="completed")

    __table_args__ = (CheckConstraint("amount_piastres > 0", name="ck_transfers_amount_positive"),)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, nullable=False)
    key = Column(String, nullable=False)
    request_hash = Column(String, nullable=False)
    status_code = Column(Integer, nullable=False)
    response_body = Column(String, nullable=False)  # JSON string
    transfer_id = Column(String, nullable=True)

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
