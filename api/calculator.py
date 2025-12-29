"""
Bill splitting calculation module.
Handles consumption calculation, cover payments, and settlement optimization.
"""

import heapq
from typing import List, Dict, Tuple


def calculate_consumption(
    people_ids: List[str],
    dishes: List[Dict],
    ratios: Dict[str, Dict[str, int]]
) -> Tuple[Dict[str, float], float]:
    """
    Calculate raw consumption for each person based on dish ratios.
    
    Edge cases handled:
    - Empty people list
    - Empty dishes list
    - Negative prices (treated as 0)
    - Dish with no one eating it (skipped)
    - Negative or zero ratios (ignored)
    
    Args:
        people_ids: List of person IDs
        dishes: List of dish dictionaries with 'id' and 'price'
        ratios: Nested dict mapping person_id -> dish_id -> ratio
        
    Returns:
        Tuple of (consumption_map, total_bill_price)
    """
    # Edge case: no people
    if not people_ids:
        return {}, 0.0
    
    raw_consumption = {pid: 0.0 for pid in people_ids}
    total_bill_price = 0.0

    # Edge case: no dishes
    if not dishes:
        return raw_consumption, 0.0

    for dish in dishes:
        # Edge case: negative or zero price
        if dish['price'] <= 0:
            continue
            
        total_bill_price += dish['price']
        
        # Get ratios for this dish
        dish_ratios = {}
        total_units = 0
        for pid in people_ids:
            # Safely get ratio (default to 0)
            r = 0
            if pid in ratios and dish['id'] in ratios[pid]:
                r = ratios[pid][dish['id']]
            # Edge case: only positive ratios are valid
            if r > 0:
                dish_ratios[pid] = r
                total_units += r
        
        # Distribute price proportionally
        # Edge case: no one eating this dish (skip distribution)
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
    
    New Logic:
    1. Covers are split equally among all people
    2. Use priority queue to process people from lowest to highest consumption
    3. If cover exceeds a person's share, the excess is redistributed to remaining people
    4. This ensures fair distribution with edge case handling
    
    Args:
        people_ids: List of person IDs
        raw_consumption: Map of person_id -> raw consumption amount
        total_bill_price: Total bill amount
        covers: List of cover payment dicts with 'person_id' and 'amount'
        
    Returns:
        Map of person_id -> final cost
    """
    # Edge case: no people
    if not people_ids:
        return {}
    
    # Edge case: no bill
    if total_bill_price <= 0:
        return {pid: 0.0 for pid in people_ids}
    
    # Calculate total cover amount
    total_covered = sum(c['amount'] for c in covers)
    
    # Edge case: covers exceed or equal total bill
    if total_covered >= total_bill_price:
        # Everyone pays nothing except those who covered
        final_cost = {pid: 0.0 for pid in people_ids}
        for c in covers:
            if c['person_id'] in final_cost:
                final_cost[c['person_id']] += c['amount']
        return final_cost
    
    # Track who covered what (for adding back at the end)
    cover_map = {pid: 0.0 for pid in people_ids}
    for c in covers:
        if c['person_id'] in cover_map:
            cover_map[c['person_id']] += c['amount']
    
    # Calculate initial equal split of cover amount
    num_people = len(people_ids)
    cover_per_person = total_covered / num_people
    
    # Create priority queue: (adjusted_cost, person_id)
    # adjusted_cost = raw consumption - equal share of cover
    heap = []
    for pid in people_ids:
        # Calculate this person's share of the bill before cover discount
        consumption_share = raw_consumption[pid]
        # Apply equal cover discount
        adjusted_cost = consumption_share - cover_per_person
        heapq.heappush(heap, (adjusted_cost, pid))
    
    # Final costs dictionary
    final_cost = {pid: 0.0 for pid in people_ids}
    
    # Process people from lowest cost to highest
    remaining_people = set(people_ids)
    remaining_cover_pool = total_covered  # Track remaining cover to redistribute
    
    while heap and remaining_people:
        adjusted_cost, pid = heapq.heappop(heap)
        
        if pid not in remaining_people:
            continue
        
        # Recalculate equal share of remaining cover among remaining people
        if len(remaining_people) > 0:
            equal_cover_share = remaining_cover_pool / len(remaining_people)
        else:
            equal_cover_share = 0
        
        # This person's actual consumption
        consumption = raw_consumption[pid]
        
        # Cost after applying cover discount
        cost_after_cover = consumption - equal_cover_share
        
        # Edge case: cover exceeds this person's consumption
        if cost_after_cover <= 0:
            # This person pays nothing from the bill portion
            final_cost[pid] = 0.0
            
            # The excess cover is redistributed
            excess = equal_cover_share - consumption
            remaining_cover_pool -= (equal_cover_share - excess)
        else:
            # Normal case: person pays reduced amount
            final_cost[pid] = cost_after_cover
            remaining_cover_pool -= equal_cover_share
        
        # Remove this person from remaining pool
        remaining_people.remove(pid)
    
    # Add back the cover amounts paid by each person
    for pid in people_ids:
        final_cost[pid] += cover_map[pid]
    
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
    
    Edge cases handled:
    - Empty people list
    - Negative payment amounts (treated as 0)
    - Multiple payments from same person (summed)
    - Person in payments but not in people_ids (ignored)
    
    Args:
        people_ids: List of person IDs
        final_costs: Map of person_id -> final cost
        payments: List of payment dicts with 'person_id' and 'amount'
        threshold: Minimum absolute value to include (filters rounding errors)
        
    Returns:
        List of balance dicts with 'id' and 'amount'
    """
    # Edge case: no people
    if not people_ids:
        return []
    
    paid_map = {pid: 0.0 for pid in people_ids}
    
    # Process payments with edge case handling
    for p in payments:
        if p['person_id'] in paid_map:
            # Edge case: negative payments treated as 0
            amount = max(0.0, p.get('amount', 0.0))
            paid_map[p['person_id']] += amount

    balances = []
    for pid in people_ids:
        net = paid_map[pid] - final_costs.get(pid, 0.0)
        # Filter out negligible amounts (floating point errors)
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
    
    Edge cases handled:
    - Empty balances list
    - All positive or all negative balances (unbalanced scenario)
    - Single person in balances
    - Very small amounts (filtered by threshold)
    
    Args:
        balances: List of balance dicts with 'id' and 'amount'
        people_names: Map of person_id -> name for output
        
    Returns:
        List of settlement dicts with debtor/creditor info and amount
    """
    # Edge case: no balances or single person
    if not balances or len(balances) <= 1:
        return []
    
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
        
        # Edge case: debtor should be negative, creditor positive
        # If not, the system is unbalanced (shouldn't happen with correct input)
        if debtor["amount"] >= -threshold or creditor["amount"] <= threshold:
            break
        
        # Transfer amount is what the debtor owes
        transfer_amount = abs(debtor["amount"])
        
        # Edge case: ensure transfer doesn't exceed what creditor is owed
        transfer_amount = min(transfer_amount, creditor["amount"])
        
        settlements.append({
            "debtor_id": debtor["id"],
            "debtor_name": people_names.get(debtor["id"], debtor["id"]),
            "creditor_id": creditor["id"],
            "creditor_name": people_names.get(creditor["id"], creditor["id"]),
            "amount": round(transfer_amount, 2)
        })
        
        # Apply the transfer
        creditor["amount"] -= transfer_amount  # Reduce what creditor is owed
        debtor["amount"] += transfer_amount    # Clear/reduce debtor's debt
        
        # Remove settled parties (those with balance ≈ 0)
        balances = [b for b in balances if abs(b["amount"]) > threshold]

    return settlements
