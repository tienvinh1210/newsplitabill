import os
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict

from .calculator import (
    calculate_consumption,
    calculate_final_costs,
    calculate_balances,
    calculate_settlements
)

app = FastAPI()

# Setup Templates
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

# --- Data Models ---
class Dish(BaseModel):
    id: str
    name: str
    price: float

class Person(BaseModel):
    id: str
    name: str

class Section1Data(BaseModel):
    people: List[Person]
    dishes: List[Dish]
    ratios: Dict[str, Dict[str, int]]

class Payment(BaseModel):
    person_id: str
    amount: float

class Cover(BaseModel):
    person_id: str
    amount: float

class BillData(BaseModel):
    section1: Section1Data
    payments: List[Payment]
    covers: List[Cover]

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/calculate")
async def calculate_split(data: BillData):
    # Map IDs to Names for final output
    people_names = {p.id: p.name for p in data.section1.people}
    people_ids = list(people_names.keys())

    # Convert Pydantic models to dicts for calculator functions
    dishes = [{"id": d.id, "price": d.price} for d in data.section1.dishes]
    covers = [{"person_id": c.person_id, "amount": c.amount} for c in data.covers]
    payments = [{"person_id": p.person_id, "amount": p.amount} for p in data.payments]

    # Step 1: Calculate consumption
    raw_consumption, total_bill_price = calculate_consumption(
        people_ids, dishes, data.section1.ratios
    )

    # Step 2: Calculate final costs with covers
    final_costs = calculate_final_costs(
        people_ids, raw_consumption, total_bill_price, covers
    )

    # Step 3: Calculate balances
    balances = calculate_balances(people_ids, final_costs, payments)

    # Step 4: Calculate settlements
    settlements = calculate_settlements(balances, people_names)

    return {"settlements": settlements}