"""
Bill splitting calculation module.
Handles consumption calculation, cover payments, and settlement optimization.
"""

from typing import List, Dict, Tuple


def calculate_consumption(
    people_ids: List[str],
    dishes: List[Dict],
    ratios: Dict[str, Dict[str, int]]
) -> Tuple[Dict[str, float], float]:
    """
    Calculate raw consumption for each person based on dish ratios.
    
    Args:
        people_ids: List of person IDs
        dishes: List of dish dictionaries with 'id' and 'price'
        ratios: Nested dict mapping person_id -> dish_id -> ratio
        
    Returns:
        Tuple of (consumption_map, total_bill_price)
    """
    raw_consumption = {pid: 0.0 for pid in people_ids}
    total_bill_price = 0.0

    for dish in dishes:
        total_bill_price += dish['price']
        
        # Get ratios for this dish
        dish_ratios = {}
        total_units = 0
        for pid in people_ids:
            # Safely get ratio (default to 0)
            r = 0
            if pid in ratios and dish['id'] in ratios[pid]:
                r = ratios[pid][dish['id']]
            if r > 0:
                dish_ratios[pid] = r
                total_units += r
        
        # Distribute price proportionally
        if total_units > 0:
            unit_price = dish['price'] / total_units
            for pid, r in dish_ratios.items():
                raw_consumption[pid] += r * unit_price

    return raw_consumption, total_bill_price


def calculate_final_costs(
    people_ids: List[str],
    raw_consumption: Dict[str, float],
    total_bill_price: float,
    covers: List[Dict]
) -> Dict[str, float]:
    """
    Calculate final costs including cover payments.
    Covers are direct payments; remaining amount is split by consumption ratios.
    
    Args:
        people_ids: List of person IDs
        raw_consumption: Map of person_id -> raw consumption amount
        total_bill_price: Total bill amount
        covers: List of cover payment dicts with 'person_id' and 'amount'
        
    Returns:
        Map of person_id -> final cost
    """
    total_covered = sum(c['amount'] for c in covers)
    cover_map = {pid: 0.0 for pid in people_ids}
    for c in covers:
        if c['person_id'] in cover_map:
            cover_map[c['person_id']] += c['amount']

    # Calculate remaining amount to split after covers
    remaining_to_split = total_bill_price - total_covered

    final_cost = {}
    for pid in people_ids:
        if remaining_to_split > 0 and total_bill_price > 0:
            # Your share = (consumption ratio) * remaining amount + your covers
            consumption_ratio = raw_consumption[pid] / total_bill_price
            final_cost[pid] = (consumption_ratio * remaining_to_split) + cover_map[pid]
        else:
            # Bill is fully covered or no bill
            final_cost[pid] = cover_map[pid]

    return final_cost


def calculate_balances(
    people_ids: List[str],
    final_costs: Dict[str, float],
    payments: List[Dict],
    threshold: float = 0.01
) -> List[Dict[str, any]]:
    """
    Calculate net balances: paid - cost.
    Positive = owed money, Negative = owes money
    
    Args:
        people_ids: List of person IDs
        final_costs: Map of person_id -> final cost
        payments: List of payment dicts with 'person_id' and 'amount'
        threshold: Minimum absolute value to include (filters rounding errors)
        
    Returns:
        List of balance dicts with 'id' and 'amount'
    """
    paid_map = {pid: 0.0 for pid in people_ids}
    for p in payments:
        if p['person_id'] in paid_map:
            paid_map[p['person_id']] += p['amount']

    balances = []
    for pid in people_ids:
        net = paid_map[pid] - final_costs[pid]
        if abs(net) > threshold:
            balances.append({"id": pid, "amount": net})

    return balances


def calculate_settlements(
    balances: List[Dict[str, any]],
    people_names: Dict[str, str]
) -> List[Dict[str, any]]:
    """
    Calculate optimal settlement transactions.
    Strategy: Each debtor pays their full debt to one creditor (1 outgoing tx per debtor).
    
    Args:
        balances: List of balance dicts with 'id' and 'amount'
        people_names: Map of person_id -> name for output
        
    Returns:
        List of settlement dicts with debtor/creditor info and amount
    """
    # Work with a copy to avoid modifying the original
    balances = [{"id": b["id"], "amount": b["amount"]} for b in balances]
    settlements = []
    
    threshold = 0.01
    max_iterations = 100
    iterations = 0

    while len(balances) > 1 and iterations < max_iterations:
        iterations += 1
        
        # Sort: most negative first (debtor), most positive last (creditor)
        balances.sort(key=lambda x: x["amount"])
        
        debtor = balances[0]
        creditor = balances[-1]
        
        # Sanity check: debtor should be negative, creditor positive
        if debtor["amount"] >= 0 or creditor["amount"] <= 0:
            break
        
        # Transfer amount is what the debtor owes
        transfer_amount = abs(debtor["amount"])
        
        settlements.append({
            "debtor_id": debtor["id"],
            "debtor_name": people_names.get(debtor["id"], debtor["id"]),
            "creditor_id": creditor["id"],
            "creditor_name": people_names.get(creditor["id"], creditor["id"]),
            "amount": round(transfer_amount, 2)
        })
        
        # Apply the transfer
        creditor["amount"] -= transfer_amount  # Reduce what creditor is owed
        debtor["amount"] += transfer_amount    # Clear debtor's debt
        
        # Remove settled parties (those with balance ≈ 0)
        balances = [b for b in balances if abs(b["amount"]) > threshold]

    return settlements
