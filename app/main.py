# -*- coding: utf-8 -*-
import json
import hashlib
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.db import make_engine, make_session_factory
from app.models import Account, Transfer, IdempotencyRecord, Base
from app.settings import Settings


class TransferRequest(BaseModel):
    model_config = {"extra": "forbid"}
    from_account_id: str
    to_account_id: str
    amount_piastres: int = Field(gt=0)
    memo: Optional[str] = Field(default=None, max_length=140)


class TokenBucket:
    def __init__(self, capacity: int, refill_per_second: float, clock):
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self.clock = clock
        self.tokens = {}
        self.last = {}
    
    def consume(self, key: str) -> tuple[bool, float]:
        now = self.clock()
        if key not in self.tokens:
            self.tokens[key] = self.capacity
            self.last[key] = now
        # refill
        elapsed = now - self.last[key]
        self.tokens[key] = min(self.capacity, self.tokens[key] + elapsed * self.refill_per_second)
        self.last[key] = now
        if self.tokens[key] >= 1.0:
            self.tokens[key] -= 1.0
            return True, 0.0
        # calculate retry after
        needed = 1.0 - self.tokens[key]
        retry_after = max(1, int(math_ceil(needed / self.refill_per_second)))
        return False, retry_after


def math_ceil(x):
    import math
    return math.ceil(x)


def problem(status_code: int, title: str, type_="about:blank", extra=None):
    body = {"type": type_, "title": title, "status": status_code}
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status_code, content=body, media_type="application/problem+json")


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    engine = make_engine(settings.database_url)
    app.state.engine = engine
    SessionLocal = make_session_factory(engine)
    bucket = TokenBucket(settings.rate_limit_capacity, settings.rate_limit_refill_per_second, settings.clock)
    
    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    def get_customer(request: Request):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None, problem(401, "Unauthorized", extra={"headers": {"WWW-Authenticate": "Bearer"}})
        token = auth[7:].strip()
        if not token:
            return None, problem(401, "Unauthorized", extra={"headers": {"WWW-Authenticate": "Bearer"}})
        if not settings.api_tokens or token not in settings.api_tokens:
            return None, problem(401, "Unauthorized", extra={"headers": {"WWW-Authenticate": "Bearer"}})
        return settings.api_tokens[token], None
    
    @app.get("/v1/accounts/{account_id}")
    def get_account(account_id: str, request: Request, db: Session = next(get_db())):
        customer_id, err = get_customer(request)
        if err:
            resp = err
            resp.headers["WWW-Authenticate"] = "Bearer"
            return resp
        acct = db.query(Account).filter(Account.id == account_id).first()
        if not acct or acct.customer_id != customer_id:
            return problem(404, "Not Found")
        return {"id": acct.id, "balance_piastres": acct.balance_piastres, "currency": "EGP"}
    
    @app.get("/v1/transfers/{transfer_id}")
    def get_transfer(transfer_id: str, request: Request, db: Session = next(get_db())):
        customer_id, err = get_customer(request)
        if err:
            resp = err
            resp.headers["WWW-Authenticate"] = "Bearer"
            return resp
        trf = db.query(Transfer).filter(Transfer.id == transfer_id).first()
        if not trf:
            return problem(404, "Not Found")
        # check ownership
        from_acct = db.query(Account).filter(Account.id == trf.from_account_id).first()
        to_acct = db.query(Account).filter(Account.id == trf.to_account_id).first()
        if not from_acct or not to_acct:
            return problem(404, "Not Found")
        if from_acct.customer_id != customer_id and to_acct.customer_id != customer_id:
            return problem(404, "Not Found")
        return {
            "id": trf.id,
            "from_account_id": trf.from_account_id,
            "to_account_id": trf.to_account_id,
            "amount_piastres": trf.amount_piastres,
            "memo": trf.memo,
            "status": trf.status
        }
    
    @app.post("/v1/transfers")
    async def create_transfer(request: Request, db: Session = next(get_db())):
        customer_id, err = get_customer(request)
        if err:
            resp = err
            resp.headers["WWW-Authenticate"] = "Bearer"
            return resp
        
        # rate limit - checked after auth, before anything else
        allowed, retry_after = bucket.consume(customer_id)
        if not allowed:
            resp = problem(429, "Too Many Requests")
            resp.headers["Retry-After"] = str(retry_after)
            return resp
        
        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return problem(400, "Bad Request")
        
        try:
            body = await request.json()
        except:
            return problem(422, "Unprocessable Entity")
        
        # check for extra fields
        try:
            req = TransferRequest(**body)
        except ValidationError:
            return problem(422, "Unprocessable Entity")
        except Exception:
            return problem(422, "Unprocessable Entity")
        
        # check body schema issues
        if not isinstance(body.get("amount_piastres"), int) or isinstance(body.get("amount_piastres"), bool):
            return problem(422, "Unprocessable Entity")
        if req.amount_piastres > settings.max_transfer_piastres:
            return problem(422, "Unprocessable Entity")
        if req.from_account_id == req.to_account_id:
            return problem(422, "Unprocessable Entity")
        
        body_str = json.dumps(body, sort_keys=True)
        body_hash = hashlib.sha256(body_str.encode()).hexdigest()
        
        # check idempotency
        idem = db.query(IdempotencyRecord).filter(
            IdempotencyRecord.customer_id == customer_id,
            IdempotencyRecord.key == idem_key
        ).first()
        if idem:
            if idem.request_hash != body_hash:
                return problem(422, "Unprocessable Entity")
            resp_body = json.loads(idem.response_body)
            resp = JSONResponse(status_code=idem.status_code, content=resp_body)
            resp.headers["Idempotent-Replayed"] = "true"
            return resp
        
        # validate accounts
        from_acct = db.query(Account).filter(Account.id == req.from_account_id).first()
        to_acct = db.query(Account).filter(Account.id == req.to_account_id).first()
        if not from_acct or from_acct.customer_id != customer_id:
            return problem(404, "Not Found")
        if not to_acct:
            return problem(422, "Unprocessable Entity")
        
        if from_acct.balance_piastres < req.amount_piastres:
            # store idempotency for 409
            resp_body = {"detail": "Insufficient funds"}
            idem_rec = IdempotencyRecord(
                customer_id=customer_id,
                key=idem_key,
                request_hash=body_hash,
                status_code=409,
                response_body=json.dumps(resp_body),
                transfer_id=None
            )
            db.add(idem_rec)
            db.commit()
            return problem(409, "Conflict")
        
        # perform transfer in transaction
        try:
            from_acct.balance_piastres -= req.amount_piastres
            to_acct.balance_piastres += req.amount_piastres
            trf_id = f"trf_{uuid.uuid4().hex[:12]}"
            trf = Transfer(
                id=trf_id,
                from_account_id=req.from_account_id,
                to_account_id=req.to_account_id,
                amount_piastres=req.amount_piastres,
                memo=req.memo,
                status="completed"
            )
            db.add(trf)
            resp_body = {
                "id": trf_id,
                "from_account_id": req.from_account_id,
                "to_account_id": req.to_account_id,
                "amount_piastres": req.amount_piastres,
                "memo": req.memo,
                "status": "completed"
            }
            idem_rec = IdempotencyRecord(
                customer_id=customer_id,
                key=idem_key,
                request_hash=body_hash,
                status_code=201,
                response_body=json.dumps(resp_body),
                transfer_id=trf_id
            )
            db.add(idem_rec)
            db.commit()
            return JSONResponse(status_code=201, content=resp_body)
        except Exception as e:
            db.rollback()
            raise
    
    return app
