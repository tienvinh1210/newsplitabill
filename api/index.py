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
# For Vercel: templates are in project root relative to api/
# For local: templates are relative to api directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates_dir = os.path.join(base_dir, "templates")
# Fallback: check if templates exists in current directory (Vercel)
if not os.path.exists(templates_dir):
    templates_dir = "templates"
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

# Normalize connection string: asyncpg accepts both postgres:// and postgresql://
# But we need to ensure SSL is enabled for Supabase/cloud databases
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgres://", 1)

# Global pool for connection reuse (works in both local and serverless)
_pool = None
_table_created = False

async def ensure_table_exists(conn):
    """Ensure the sessions table exists (for Vercel where startup events don't run)"""
    global _table_created
    if _table_created:
        return
    try:
        # For session poolers, just use CREATE TABLE IF NOT EXISTS
        # This is simpler and more reliable than checking information_schema
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                state JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        print("Ensured sessions table exists")
        _table_created = True
    except Exception as e:
        # If table creation fails, it might already exist
        # Don't fail the whole request, but log the error
        print(f"Warning: Could not ensure table exists: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        # Set _table_created anyway to avoid retrying on every request
        # If table doesn't exist, the INSERT will fail with a clear error
        _table_created = True

async def get_pool():
    global _pool
    # In serverless (Vercel), connection pooling can be problematic
    # Create a new pool if it doesn't exist or if we're in serverless
    if _pool is None or os.getenv("VERCEL"):
        try:
            if _pool and os.getenv("VERCEL"):
                # Close old pool in serverless before creating new one
                try:
                    await _pool.close()
                except:
                    pass
            
            # Determine if we need SSL (Supabase and most cloud DBs require it)
            # Check if the host is not localhost/127.0.0.1
            needs_ssl = True  # Default to SSL for safety
            if "localhost" in DATABASE_URL or "127.0.0.1" in DATABASE_URL:
                needs_ssl = False
            
            # Check if using session pooler (usually has "pooler" in hostname or port 6543)
            is_pooler = "pooler" in DATABASE_URL.lower() or ":6543" in DATABASE_URL
            
            # For Supabase, ensure SSL is enabled
            # asyncpg accepts ssl=True/False, or we can add ?sslmode=require to the URL
            # If connection string doesn't already have sslmode, add it for cloud DBs
            db_url = DATABASE_URL
            if needs_ssl and "sslmode" not in db_url:
                separator = "&" if "?" in db_url else "?"
                db_url = f"{db_url}{separator}sslmode=require"
            
            # For session poolers, use smaller pool and shorter timeout
            # Session poolers handle connection management differently
            pool_size = 1 if is_pooler else 2
            timeout = 5 if is_pooler else 10
            
            # Create pool with SSL for cloud databases
            _pool = await asyncpg.create_pool(
                db_url, 
                min_size=1, 
                max_size=pool_size,  # Smaller pool for session poolers
                command_timeout=timeout  # Shorter timeout for session poolers
            )
        except Exception as e:
            print(f"Error creating database pool: {str(e)}")
            raise
    return _pool

# Startup event - only run in non-serverless environments
# Vercel serverless functions don't support startup events reliably
if not os.getenv("VERCEL"):
    @app.on_event("startup")
    async def startup():
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

# Shutdown event - only in non-serverless
if not os.getenv("VERCEL"):
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
    try:
        # Validate payload
        if not payload or not payload.state:
            raise HTTPException(status_code=400, detail="Invalid payload: state is required")
        
        pool = await get_pool()
        session_id = uuid.uuid4().hex
        
        # Check if using session pooler
        is_pooler = "pooler" in DATABASE_URL.lower() or ":6543" in DATABASE_URL
        
        # Prepare the state JSON
        try:
            state_json = json.dumps(payload.state)
            print(f"Creating session {session_id} with state size: {len(state_json)} bytes")
        except Exception as json_error:
            print(f"Error serializing state to JSON: {json_error}")
            raise HTTPException(status_code=400, detail=f"Invalid state data: {str(json_error)}")
        
        async with pool.acquire() as conn:
            # Ensure table exists first
            await ensure_table_exists(conn)
            
            # For session poolers, execute directly (each execute is auto-committed)
            # For regular connections, also execute directly (asyncpg auto-commits by default)
            try:
                result = await conn.execute(
                    "INSERT INTO sessions (id, state) VALUES ($1, $2::jsonb)",
                    session_id,
                    state_json,
                )
                print(f"Session created successfully: {result}")
            except Exception as insert_error:
                error_msg = str(insert_error)
                print(f"INSERT failed: {error_msg}")
                print(f"Error type: {type(insert_error).__name__}")
                # Check if it's a table doesn't exist error
                if "does not exist" in error_msg.lower() or "relation" in error_msg.lower():
                    print("Table might not exist, trying to create it again...")
                    _table_created = False  # Reset flag to retry table creation
                    await ensure_table_exists(conn)
                    # Retry the insert
                    result = await conn.execute(
                        "INSERT INTO sessions (id, state) VALUES ($1, $2::jsonb)",
                        session_id,
                        state_json,
                    )
                    print(f"Session created after table creation: {result}")
                else:
                    raise
        
        return {"id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"Error creating session: {error_msg}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback_str = traceback.format_exc()
        print(f"Traceback: {traceback_str}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {error_msg}")

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    try:
        pool = await get_pool()
        is_pooler = "pooler" in DATABASE_URL.lower() or ":6543" in DATABASE_URL
        
        async with pool.acquire() as conn:
            # Ensure table exists
            await ensure_table_exists(conn)
            # Session poolers may not support explicit transactions
            if is_pooler:
                row = await conn.fetchrow("SELECT state FROM sessions WHERE id=$1", session_id)
            else:
                async with conn.transaction():
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
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting session: {str(e)}")
        print(f"Session ID: {session_id}")
        raise HTTPException(status_code=500, detail=f"Failed to get session: {str(e)}")

@app.put("/sessions/{session_id}")
async def update_session(session_id: str, payload: SessionPayload):
    try:
        pool = await get_pool()
        is_pooler = "pooler" in DATABASE_URL.lower() or ":6543" in DATABASE_URL
        
        async with pool.acquire() as conn:
            # Ensure table exists
            await ensure_table_exists(conn)
            # Session poolers may not support explicit transactions
            if is_pooler:
                result = await conn.execute(
                    "UPDATE sessions SET state=$1::jsonb, updated_at=NOW() WHERE id=$2",
                    json.dumps(payload.state),
                    session_id,
                )
            else:
                async with conn.transaction():
                    result = await conn.execute(
                        "UPDATE sessions SET state=$1::jsonb, updated_at=NOW() WHERE id=$2",
                        json.dumps(payload.state),
                        session_id,
                    )
        if result.endswith("UPDATE 0"):
            raise HTTPException(status_code=404, detail="Session not found")
        return {"id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating session: {str(e)}")
        print(f"Session ID: {session_id}")
        print(f"Payload state keys: {list(payload.state.keys()) if isinstance(payload.state, dict) else 'N/A'}")
        raise HTTPException(status_code=500, detail=f"Failed to update session: {str(e)}")

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
# Vercel's @vercel/python runtime automatically detects FastAPI apps
# The app variable is automatically used as the handler