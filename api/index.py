import os
import uuid
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict
import asyncpg
import asyncio

app = FastAPI()

# Setup Templates
# For Vercel: templates are in project root
# For local: templates are relative to api directory
if os.path.exists("templates"):
    templates_dir = "templates"
else:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(base_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)

# --- Database ---
# Use DATABASE_URL from environment variable
# For local development: export DATABASE_URL="postgres://user:password@localhost:5432/dbname"
# For Vercel: Set DATABASE_URL in project environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is required. "
        "Set it for local development or configure it in Vercel environment variables."
    )

# Global pool for connection reuse (works in both local and serverless)
_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool

@app.on_event("startup")
async def startup():
    # Only create table in non-serverless environments
    # In Vercel, you should create the table manually via migration or SQL tool
    if not os.getenv("VERCEL"):
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        state JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
        except Exception as e:
            print(f"Warning: Could not create table (might already exist): {e}")

@app.on_event("shutdown")
async def shutdown():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

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

class SessionPayload(BaseModel):
    state: dict

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/sessions")
async def create_session(payload: SessionPayload):
    pool = await get_pool()
    session_id = uuid.uuid4().hex
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sessions (id, state) VALUES ($1, $2::jsonb)",
            session_id,
            json.dumps(payload.state),
        )
    return {"id": session_id}

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT state FROM sessions WHERE id=$1", session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    # state is stored as JSONB; ensure we return a dict
    raw_state = row["state"]
    if isinstance(raw_state, str):
        state = json.loads(raw_state)
    else:
        state = raw_state
    return {"id": session_id, "state": state}

@app.put("/sessions/{session_id}")
async def update_session(session_id: str, payload: SessionPayload):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE sessions SET state=$1::jsonb, updated_at=NOW() WHERE id=$2",
            json.dumps(payload.state),
            session_id,
        )
    if result.endswith("UPDATE 0"):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"id": session_id}

@app.post("/calculate")
async def calculate_split(data: BillData):
    # Map IDs to Names for final output
    people_names = {p.id: p.name for p in data.section1.people}
    people_ids = list(people_names.keys())

    # ---------------------------------------------------------
    # STEP 1: CALCULATE CONSUMPTION (Who ate what?)
    # ---------------------------------------------------------
    raw_consumption = {pid: 0.0 for pid in people_ids}
    total_bill_price = 0.0

    for dish in data.section1.dishes:
        total_bill_price += dish.price
        
        # Get ratios for this dish
        dish_ratios = {}
        total_units = 0
        for pid in people_ids:
            # Safely get ratio (default to 0)
            r = 0
            if pid in data.section1.ratios and dish.id in data.section1.ratios[pid]:
                r = data.section1.ratios[pid][dish.id]
            if r > 0:
                dish_ratios[pid] = r
                total_units += r
        
        # Distribute price
        if total_units > 0:
            unit_price = dish.price / total_units
            for pid, r in dish_ratios.items():
                raw_consumption[pid] += r * unit_price

    # ---------------------------------------------------------
    # STEP 2: HANDLE COVERS ("Bao Bữa")
    # Logic: "Covers" act as a discount on the group's consumption cost.
    # The person covering voluntarily takes on that cost.
    # ---------------------------------------------------------
    total_covered = sum(c.amount for c in data.covers)
    cover_map = {pid: 0.0 for pid in people_ids}
    for c in data.covers:
        if c.person_id in cover_map:
            cover_map[c.person_id] += c.amount

    # Calculate Discount Multiplier
    # If Total Bill is 100 and 20 is covered, only 80 is split by ratios.
    if total_bill_price > 0 and total_covered < total_bill_price:
        multiplier = (total_bill_price - total_covered) / total_bill_price
    else:
        multiplier = 0.0 # Fully covered or invalid

    final_cost = {}
    for pid in people_ids:
        # Your Cost = (What you ate * Multiplier) + (What you voluntarily covered)
        final_cost[pid] = (raw_consumption[pid] * multiplier) + cover_map[pid]

    # ---------------------------------------------------------
    # STEP 3: CALCULATE NET BALANCES
    # Balance = Paid - Cost
    # (+) Positive: You paid more than your share (You are owed money)
    # (-) Negative: You paid less than your share (You owe money)
    # ---------------------------------------------------------
    paid_map = {pid: 0.0 for pid in people_ids}
    for p in data.payments:
        if p.person_id in paid_map:
            paid_map[p.person_id] += p.amount

    balances = []
    for pid in people_ids:
        net = paid_map[pid] - final_cost[pid]
        # Filter out negligible amounts (floating point errors)
        if abs(net) > 0.01:
            balances.append({"id": pid, "amount": net})

    # ---------------------------------------------------------
    # STEP 4: SETTLEMENT ALGORITHM (Pass-the-Debt)
    # Constraint: Minimize transfers & Max 1 Outgoing per person.
    # Strategy: The Deepest Debtor pays their *entire* debt to the Highest Creditor.
    # This clears the Debtor completely (1 outgoing tx) and passes any surplus debt to the Creditor.
    # ---------------------------------------------------------
    settlements = []

    # Safety break to prevent infinite loops
    steps = 0
    while len(balances) > 1 and steps < 100:
        steps += 1
        
        # Sort by amount:
        # index 0  = Most Negative (Deepest Debtor)
        # index -1 = Most Positive (Highest Creditor)
        balances.sort(key=lambda x: x["amount"])

        debtor = balances[0]
        creditor = balances[-1]

        # The amount to transfer is exactly what the Debtor owes.
        # This ensures Debtor reaches 0.00 and leaves the pool.
        transfer_amount = abs(debtor["amount"])

        # Format String
        settlements.append({
            "debtor_id": debtor["id"],
            "debtor_name": people_names[debtor["id"]],
            "creditor_id": creditor["id"],
            "creditor_name": people_names[creditor["id"]],
            "amount": transfer_amount
        })

        # Execute Transfer
        creditor["amount"] += debtor["amount"] # e.g. (+100) + (-20) = +80
        
        # Remove Debtor (now 0)
        balances.pop(0)

        # Check if Creditor is now settled (approx 0)
        # Note: We must re-check the creditor because they might have dipped to 0
        if abs(creditor["amount"]) < 0.01:
            # Depending on list length, creditor might have shifted index.
            # Easiest way is to just let the next loop handle it or remove if found.
            balances = [b for b in balances if abs(b["amount"]) > 0.01]

    return {"settlements": settlements}

# Export handler for Vercel
handler = app