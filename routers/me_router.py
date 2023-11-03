from typing import Annotated

from _decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy import select, update, insert
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import JSONResponse

from dal import accounts_crud
from data.models.account import Account
from data.models.currency import Currency
from data.models.transaction import Transaction
from data.models.user import User
from data.schemas.account import GetAccountScheme, ReplData, CreateSelfAccount, ReplAcc
from data.schemas.currency import GetCurrencyScheme
from data.schemas.transaction import GetTransactionScheme
from data.schemas.user import GetUserScheme
from dependencies import get_current_user, get_db

me_router = APIRouter(prefix="/me", tags=["Me"])


@me_router.get("")
def profile(current_user: User = Depends(get_current_user)) -> GetUserScheme:
    return current_user


@me_router.get("/accounts")
async def get_my_accounts(current_user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)) -> list[GetAccountScheme]:
    accs = accounts_crud.get_accounts_by_user(db, user_id=current_user.id, skip=0, limit=100)
    if not accs:
        raise HTTPException(status_code=404, detail="You do not have accounts!")

    return accs


@me_router.get("/currencies", response_model=list[GetCurrencyScheme])
async def get_currencies(
        db: Session = Depends(get_db)):
    query = select(Currency)
    result = db.execute(query).scalars().all()
    return result


@me_router.post("/replenishment")
async def replenish_balance(repl: Annotated[ReplData, Body()], user: User = Depends(get_current_user),
                            db: Session = Depends(get_db), ):
    try:
        query = update(User).where(User.id == user.id).values(balance=User.balance + Decimal(repl.amount))
        db.execute(query)
        db.commit()
        return JSONResponse(status_code=200, content={"detail": "replenishment was successful"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@me_router.post("/accounts")
async def create_account(acc: Annotated[CreateSelfAccount, Body()], user: User = Depends(get_current_user),
                         db: Session = Depends(get_db), ):
    _curr = select(Currency).where(Currency.id == acc.default_currency_id)

    if not db.execute(_curr).scalar():
        return JSONResponse({"detail": "currency not found!"}, status_code=404)
    else:

        try:
            query = insert(Account).values(user_id=user.id,
                                           default_currency_id=acc.default_currency_id,
                                           balance=0)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"{e}")

        db.execute(query)

        db.commit()

        return JSONResponse(content={"detail": "account was created!"}, status_code=201)


@me_router.post("/accounts/repl")
async def replenish_account(data: Annotated[ReplAcc, Body()], db: Session = Depends(get_db),
                            user: User = Depends(get_current_user)):
    if data.amount > user.balance:
        return HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient funds")

    query1 = select(Account.default_currency_id).where(Account.id == data.account_id)
    acc = db.execute(query1).scalar()

    query2 = select(Currency.exchange_rate).where(Currency.id == acc)

    exchange_rate = db.execute(query2).scalar()

    query = update(Account).where(Account.id == data.account_id).values(
        balance=Account.balance + data.amount / float(exchange_rate))
    query4 = update(User).where(User.id == user.id).values(balance=float(user.balance) - data.amount)

    try:
        db.execute(query)
        db.execute(query4)
        db.commit()
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"detail": "something went wrong!"})

    return JSONResponse(content={"detail": "The account has been topped up"}, status_code=200)


@me_router.get("/transfers", response_model=list[GetTransactionScheme])
def get_remmitances(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query1 = select(Account.id).where(Account.user_id == user.id)
    accs = db.execute(query1).scalars().all()
    print(accs)
    query = select(Transaction).where(Transaction.sender_account_id in accs)
    print(query)
    result = db.execute(query).scalars().all()
    print(result)
    return result


@me_router.get("/transfers/send")
def get_sended_remmitances():
    pass


@me_router.get("/transfers/received")
def get_received_remmitances():
    pass


@me_router.post("/transfers/make")
def transfer():
    pass
