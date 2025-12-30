"""
Unit tests for bill splitting calculator module.
"""

import unittest
import sys
import os

# Add parent directory to path to import calculator module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.calculator import (
    calculate_consumption,
    calculate_final_costs,
    calculate_balances,
    calculate_settlements
)


class TestCalculateConsumption(unittest.TestCase):
    """Test consumption calculation logic."""
    
    def test_equal_split(self):
        """Test equal split of a single dish."""
        people_ids = ["p1", "p2"]
        dishes = [{"id": "d1", "price": 100.0}]
        ratios = {
            "p1": {"d1": 1},
            "p2": {"d1": 1}
        }
        
        consumption, total = calculate_consumption(people_ids, dishes, ratios)
        
        self.assertEqual(total, 100.0)
        self.assertEqual(consumption["p1"], 50.0)
        self.assertEqual(consumption["p2"], 50.0)
    
    def test_unequal_split(self):
        """Test unequal split with different ratios."""
        people_ids = ["p1", "p2"]
        dishes = [{"id": "d1", "price": 90.0}]
        ratios = {
            "p1": {"d1": 2},
            "p2": {"d1": 1}
        }
        
        consumption, total = calculate_consumption(people_ids, dishes, ratios)
        
        self.assertEqual(total, 90.0)
        self.assertEqual(consumption["p1"], 60.0)  # 2/3 of 90
        self.assertEqual(consumption["p2"], 30.0)  # 1/3 of 90
    
    def test_multiple_dishes(self):
        """Test consumption across multiple dishes."""
        people_ids = ["p1", "p2", "p3"]
        dishes = [
            {"id": "d1", "price": 60.0},
            {"id": "d2", "price": 40.0}
        ]
        ratios = {
            "p1": {"d1": 1, "d2": 0},
            "p2": {"d1": 1, "d2": 2},
            "p3": {"d1": 1, "d2": 1}
        }
        
        consumption, total = calculate_consumption(people_ids, dishes, ratios)
        
        self.assertEqual(total, 100.0)
        self.assertEqual(consumption["p1"], 20.0)   # d1: 60/3 = 20
        self.assertAlmostEqual(consumption["p2"], 46.67, places=2)  # d1: 20, d2: 40*2/3 = 26.67
        self.assertAlmostEqual(consumption["p3"], 33.33, places=2)  # d1: 20, d2: 40*1/3 = 13.33
    
    def test_person_not_eating(self):
        """Test when a person doesn't eat anything."""
        people_ids = ["p1", "p2"]
        dishes = [{"id": "d1", "price": 50.0}]
        ratios = {
            "p1": {"d1": 1},
            "p2": {}  # p2 doesn't eat
        }
        
        consumption, total = calculate_consumption(people_ids, dishes, ratios)
        
        self.assertEqual(consumption["p1"], 50.0)
        self.assertEqual(consumption["p2"], 0.0)
    
    def test_empty_dishes(self):
        """Test with no dishes."""
        people_ids = ["p1", "p2"]
        dishes = []
        ratios = {}
        
        consumption, total = calculate_consumption(people_ids, dishes, ratios)
        
        self.assertEqual(total, 0.0)
        self.assertEqual(consumption["p1"], 0.0)
        self.assertEqual(consumption["p2"], 0.0)
    
    def test_empty_people(self):
        """Edge case: no people."""
        people_ids = []
        dishes = [{"id": "d1", "price": 100.0}]
        ratios = {}
        
        consumption, total = calculate_consumption(people_ids, dishes, ratios)
        
        self.assertEqual(total, 0.0)
        self.assertEqual(consumption, {})
    
    def test_negative_price(self):
        """Edge case: negative price should be ignored."""
        people_ids = ["p1", "p2"]
        dishes = [
            {"id": "d1", "price": 100.0},
            {"id": "d2", "price": -50.0}  # Invalid
        ]
        ratios = {
            "p1": {"d1": 1, "d2": 1},
            "p2": {"d1": 1, "d2": 1}
        }
        
        consumption, total = calculate_consumption(people_ids, dishes, ratios)
        
        self.assertEqual(total, 100.0)  # Only d1 counted
        self.assertEqual(consumption["p1"], 50.0)
        self.assertEqual(consumption["p2"], 50.0)
    
    def test_dish_no_eaters(self):
        """Edge case: dish with no one eating it."""
        people_ids = ["p1", "p2"]
        dishes = [
            {"id": "d1", "price": 80.0},
            {"id": "d2", "price": 20.0}  # No one eats this
        ]
        ratios = {
            "p1": {"d1": 1},
            "p2": {"d1": 1}
        }
        
        consumption, total = calculate_consumption(people_ids, dishes, ratios)
        
        self.assertEqual(total, 100.0)  # Both dishes counted in total
        self.assertEqual(consumption["p1"], 40.0)  # Only d1 distributed
        self.assertEqual(consumption["p2"], 40.0)


class TestCalculateFinalCosts(unittest.TestCase):
    """Test final cost calculation with covers."""
    
    def test_no_covers(self):
        """Test when nobody covers anything."""
        people_ids = ["p1", "p2"]
        raw_consumption = {"p1": 60.0, "p2": 40.0}
        total_bill = 100.0
        covers = []
        
        final_costs = calculate_final_costs(people_ids, raw_consumption, total_bill, covers)
        
        self.assertEqual(final_costs["p1"], 60.0)
        self.assertEqual(final_costs["p2"], 40.0)
    
    def test_equal_cover_split(self):
        """Test cover split equally among all people."""
        people_ids = ["p1", "p2", "p3"]
        raw_consumption = {"p1": 30.0, "p2": 30.0, "p3": 30.0}
        total_bill = 90.0
        covers = [{"person_id": "p1", "amount": 30.0}]
        
        final_costs = calculate_final_costs(people_ids, raw_consumption, total_bill, covers)
        
        # Cover of 30 split equally: 10 each
        # p1: 30 - 10 + 30(cover) = 50
        # p2: 30 - 10 = 20
        # p3: 30 - 10 = 20
        self.assertEqual(final_costs["p1"], 50.0)
        self.assertEqual(final_costs["p2"], 20.0)
        self.assertEqual(final_costs["p3"], 20.0)
        self.assertAlmostEqual(sum(final_costs.values()), 90.0, places=2)
    
    def test_cover_exceeds_person_cost(self):
        """Test when cover share exceeds a person's consumption (priority queue logic)."""
        people_ids = ["p1", "p2", "p3"]
        raw_consumption = {"p1": 10.0, "p2": 40.0, "p3": 50.0}
        total_bill = 100.0
        covers = [{"person_id": "p3", "amount": 60.0}]
        
        final_costs = calculate_final_costs(people_ids, raw_consumption, total_bill, covers)
        
        # Cover of 60 should be split, starting with lowest consumption
        # Initial equal split: 20 each
        # p1 only consumed 10, so excess 10 redistributed
        # Expected: p1 pays 0 (10-10) + 0, p2 and p3 share remaining
        self.assertEqual(final_costs["p1"], 0.0)
        # Remaining people handle the rest
        self.assertGreater(final_costs["p2"], 0)
        self.assertGreater(final_costs["p3"], 0)
        self.assertAlmostEqual(sum(final_costs.values()), 100.0, places=2)
    
    def test_full_cover(self):
        """Test when someone covers the entire bill."""
        people_ids = ["p1", "p2"]
        raw_consumption = {"p1": 60.0, "p2": 40.0}
        total_bill = 100.0
        covers = [{"person_id": "p1", "amount": 100.0}]
        
        final_costs = calculate_final_costs(people_ids, raw_consumption, total_bill, covers)
        
        # Bill fully covered, only coverer pays
        self.assertEqual(final_costs["p1"], 100.0)
        self.assertEqual(final_costs["p2"], 0.0)
    
    def test_multiple_covers(self):
        """Test when multiple people cover."""
        people_ids = ["p1", "p2", "p3"]
        raw_consumption = {"p1": 30.0, "p2": 30.0, "p3": 40.0}
        total_bill = 100.0
        covers = [
            {"person_id": "p1", "amount": 20.0},
            {"person_id": "p2", "amount": 10.0}
        ]
        
        final_costs = calculate_final_costs(people_ids, raw_consumption, total_bill, covers)
        
        # Total cover: 30, split equally: 10 each
        # p1: 30 - 10 + 20 = 40
        # p2: 30 - 10 + 10 = 30
        # p3: 40 - 10 = 30
        self.assertEqual(final_costs["p1"], 40.0)
        self.assertEqual(final_costs["p2"], 30.0)
        self.assertEqual(final_costs["p3"], 30.0)
        self.assertAlmostEqual(sum(final_costs.values()), 100.0, places=2)
    
    def test_cover_exceeds_bill(self):
        """Edge case: cover exceeds total bill."""
        people_ids = ["p1", "p2"]
        raw_consumption = {"p1": 50.0, "p2": 50.0}
        total_bill = 100.0
        covers = [{"person_id": "p1", "amount": 150.0}]
        
        final_costs = calculate_final_costs(people_ids, raw_consumption, total_bill, covers)
        
        # Cover exceeds bill, only coverer pays
        self.assertEqual(final_costs["p1"], 150.0)
        self.assertEqual(final_costs["p2"], 0.0)
    
    def test_empty_people(self):
        """Edge case: no people."""
        people_ids = []
        raw_consumption = {}
        total_bill = 100.0
        covers = []
        
        final_costs = calculate_final_costs(people_ids, raw_consumption, total_bill, covers)
        
        self.assertEqual(final_costs, {})
    
    def test_zero_bill(self):
        """Edge case: zero bill."""
        people_ids = ["p1", "p2"]
        raw_consumption = {"p1": 0.0, "p2": 0.0}
        total_bill = 0.0
        covers = []
        
        final_costs = calculate_final_costs(people_ids, raw_consumption, total_bill, covers)
        
        self.assertEqual(final_costs["p1"], 0.0)
        self.assertEqual(final_costs["p2"], 0.0)


class TestCalculateBalances(unittest.TestCase):
    """Test balance calculation logic."""
    
    def test_balanced_payment(self):
        """Test when everyone pays exactly their share."""
        people_ids = ["p1", "p2"]
        final_costs = {"p1": 60.0, "p2": 40.0}
        payments = [
            {"person_id": "p1", "amount": 60.0},
            {"person_id": "p2", "amount": 40.0}
        ]
        
        balances = calculate_balances(people_ids, final_costs, payments)
        
        self.assertEqual(len(balances), 0)  # No imbalances
    
    def test_one_person_pays_all(self):
        """Test when one person pays the entire bill."""
        people_ids = ["p1", "p2"]
        final_costs = {"p1": 60.0, "p2": 40.0}
        payments = [
            {"person_id": "p1", "amount": 100.0},
            {"person_id": "p2", "amount": 0.0}
        ]
        
        balances = calculate_balances(people_ids, final_costs, payments)
        
        self.assertEqual(len(balances), 2)
        # Find p1 and p2 in balances
        p1_balance = next(b for b in balances if b["id"] == "p1")
        p2_balance = next(b for b in balances if b["id"] == "p2")
        
        self.assertEqual(p1_balance["amount"], 40.0)   # Paid 100, cost 60, owed 40
        self.assertEqual(p2_balance["amount"], -40.0)  # Paid 0, cost 40, owes 40
    
    def test_floating_point_threshold(self):
        """Test that small rounding errors are filtered out."""
        people_ids = ["p1", "p2"]
        final_costs = {"p1": 50.0, "p2": 50.0}
        payments = [
            {"person_id": "p1", "amount": 50.005},  # Tiny overpayment
            {"person_id": "p2", "amount": 49.995}   # Tiny underpayment
        ]
        
        balances = calculate_balances(people_ids, final_costs, payments, threshold=0.01)
        
        self.assertEqual(len(balances), 0)  # Both within threshold
    
    def test_complex_scenario(self):
        """Test complex payment scenario with multiple people."""
        people_ids = ["p1", "p2", "p3"]
        final_costs = {"p1": 30.0, "p2": 40.0, "p3": 30.0}
        payments = [
            {"person_id": "p1", "amount": 50.0},
            {"person_id": "p2", "amount": 50.0},
            {"person_id": "p3", "amount": 0.0}
        ]
        
        balances = calculate_balances(people_ids, final_costs, payments)
        
        self.assertEqual(len(balances), 3)
        p1_balance = next(b for b in balances if b["id"] == "p1")
        p2_balance = next(b for b in balances if b["id"] == "p2")
        p3_balance = next(b for b in balances if b["id"] == "p3")
        
        self.assertEqual(p1_balance["amount"], 20.0)   # Paid 50, cost 30
        self.assertEqual(p2_balance["amount"], 10.0)   # Paid 50, cost 40
        self.assertEqual(p3_balance["amount"], -30.0)  # Paid 0, cost 30
    
    def test_empty_people(self):
        """Edge case: no people."""
        people_ids = []
        final_costs = {}
        payments = []
        
        balances = calculate_balances(people_ids, final_costs, payments)
        
        self.assertEqual(len(balances), 0)
    
    def test_negative_payment(self):
        """Edge case: negative payment treated as 0."""
        people_ids = ["p1", "p2"]
        final_costs = {"p1": 50.0, "p2": 50.0}
        payments = [
            {"person_id": "p1", "amount": 50.0},
            {"person_id": "p2", "amount": -10.0}  # Invalid
        ]
        
        balances = calculate_balances(people_ids, final_costs, payments)
        
        # p2 treated as paying 0
        p2_balance = next(b for b in balances if b["id"] == "p2")
        self.assertEqual(p2_balance["amount"], -50.0)


class TestCalculateSettlements(unittest.TestCase):
    """Test settlement optimization logic."""
    
    def test_simple_two_person(self):
        """Test simple settlement between two people."""
        balances = [
            {"id": "p1", "amount": 40.0},
            {"id": "p2", "amount": -40.0}
        ]
        people_names = {"p1": "Alice", "p2": "Bob"}
        
        settlements = calculate_settlements(balances, people_names)
        
        self.assertEqual(len(settlements), 1)
        self.assertEqual(settlements[0]["debtor_id"], "p2")
        self.assertEqual(settlements[0]["creditor_id"], "p1")
        self.assertEqual(settlements[0]["amount"], 40.0)
    
    def test_three_person_chain(self):
        """Test settlement with three people in a chain."""
        balances = [
            {"id": "p1", "amount": 30.0},
            {"id": "p2", "amount": -10.0},
            {"id": "p3", "amount": -20.0}
        ]
        people_names = {"p1": "Alice", "p2": "Bob", "p3": "Charlie"}
        
        settlements = calculate_settlements(balances, people_names)
        
        # Should have 2 settlements
        self.assertEqual(len(settlements), 2)
        
        # p3 owes the most (-20), should pay p1 (who is owed the most)
        self.assertEqual(settlements[0]["debtor_id"], "p3")
        self.assertEqual(settlements[0]["creditor_id"], "p1")
        self.assertEqual(settlements[0]["amount"], 20.0)
        
        # p2 owes -10, should pay remaining 10 to p1
        self.assertEqual(settlements[1]["debtor_id"], "p2")
        self.assertEqual(settlements[1]["creditor_id"], "p1")
        self.assertEqual(settlements[1]["amount"], 10.0)
    
    def test_multiple_creditors(self):
        """Test settlement with multiple creditors."""
        balances = [
            {"id": "p1", "amount": 20.0},
            {"id": "p2", "amount": 10.0},
            {"id": "p3", "amount": -30.0}
        ]
        people_names = {"p1": "Alice", "p2": "Bob", "p3": "Charlie"}
        
        settlements = calculate_settlements(balances, people_names)
        
        # p3 owes 30 total
        # Should pay p1 first (highest creditor) for 20
        # Then pay p2 for remaining 10
        self.assertEqual(len(settlements), 2)
        
        total_p3_pays = sum(s["amount"] for s in settlements if s["debtor_id"] == "p3")
        self.assertEqual(total_p3_pays, 30.0)
    
    def test_complex_scenario(self):
        """Test complex settlement with multiple debtors and creditors."""
        balances = [
            {"id": "p1", "amount": 50.0},
            {"id": "p2", "amount": -20.0},
            {"id": "p3", "amount": -30.0}
        ]
        people_names = {"p1": "Alice", "p2": "Bob", "p3": "Charlie"}
        
        settlements = calculate_settlements(balances, people_names)
        
        self.assertEqual(len(settlements), 2)
        
        # Verify all debtors pay correct amounts
        p2_pays = sum(s["amount"] for s in settlements if s["debtor_id"] == "p2")
        p3_pays = sum(s["amount"] for s in settlements if s["debtor_id"] == "p3")
        
        self.assertEqual(p2_pays, 20.0)
        self.assertEqual(p3_pays, 30.0)
    
    def test_already_balanced(self):
        """Test when balances are already settled."""
        balances = []
        people_names = {"p1": "Alice", "p2": "Bob"}
        
        settlements = calculate_settlements(balances, people_names)
        
        self.assertEqual(len(settlements), 0)
    
    def test_rounding_precision(self):
        """Test that amounts are properly rounded."""
        balances = [
            {"id": "p1", "amount": 33.333333},
            {"id": "p2", "amount": -33.333333}
        ]
        people_names = {"p1": "Alice", "p2": "Bob"}
        
        settlements = calculate_settlements(balances, people_names)
        
        self.assertEqual(len(settlements), 1)
        self.assertEqual(settlements[0]["amount"], 33.33)
    
    def test_single_person(self):
        """Edge case: single person with balance."""
        balances = [{"id": "p1", "amount": 50.0}]
        people_names = {"p1": "Alice"}
        
        settlements = calculate_settlements(balances, people_names)
        
        self.assertEqual(len(settlements), 0)
    
    def test_all_positive_balances(self):
        """Edge case: all positive balances (everyone is owed money)."""
        balances = [
            {"id": "p1", "amount": 30.0},
            {"id": "p2", "amount": 20.0}
        ]
        people_names = {"p1": "Alice", "p2": "Bob"}
        
        settlements = calculate_settlements(balances, people_names)
        
        # No settlements possible if no one owes money
        self.assertEqual(len(settlements), 0)
    
    def test_all_negative_balances(self):
        """Edge case: all negative balances (everyone owes money)."""
        balances = [
            {"id": "p1", "amount": -30.0},
            {"id": "p2", "amount": -20.0}
        ]
        people_names = {"p1": "Alice", "p2": "Bob"}
        
        settlements = calculate_settlements(balances, people_names)
        
        # No settlements possible if no one is owed money
        self.assertEqual(len(settlements), 0)


class TestIntegration(unittest.TestCase):
    """End-to-end integration tests."""
    
    def test_full_flow_simple(self):
        """Test complete flow with simple scenario."""
        # Setup
        people_ids = ["p1", "p2"]
        dishes = [{"id": "d1", "price": 100.0}]
        ratios = {"p1": {"d1": 1}, "p2": {"d1": 1}}
        covers = []
        payments = [{"person_id": "p1", "amount": 100.0}]
        people_names = {"p1": "Alice", "p2": "Bob"}
        
        # Execute
        consumption, total = calculate_consumption(people_ids, dishes, ratios)
        final_costs = calculate_final_costs(people_ids, consumption, total, covers)
        balances = calculate_balances(people_ids, final_costs, payments)
        settlements = calculate_settlements(balances, people_names)
        
        # Verify
        self.assertEqual(len(settlements), 1)
        self.assertEqual(settlements[0]["debtor_name"], "Bob")
        self.assertEqual(settlements[0]["creditor_name"], "Alice")
        self.assertEqual(settlements[0]["amount"], 50.0)
    
    def test_full_flow_with_covers(self):
        """Test complete flow with covers."""
        # Setup
        people_ids = ["p1", "p2", "p3"]
        dishes = [{"id": "d1", "price": 90.0}]
        ratios = {
            "p1": {"d1": 1},
            "p2": {"d1": 1},
            "p3": {"d1": 1}
        }
        covers = [{"person_id": "p1", "amount": 30.0}]
        payments = [
            {"person_id": "p1", "amount": 60.0},
            {"person_id": "p2", "amount": 30.0}
        ]
        people_names = {"p1": "Alice", "p2": "Bob", "p3": "Charlie"}
        
        # Execute
        consumption, total = calculate_consumption(people_ids, dishes, ratios)
        final_costs = calculate_final_costs(people_ids, consumption, total, covers)
        balances = calculate_balances(people_ids, final_costs, payments)
        settlements = calculate_settlements(balances, people_names)
        
        # Verify final costs sum to total
        self.assertAlmostEqual(sum(final_costs.values()), 90.0, places=2)
        
        # Verify settlements balance out
        total_settled = sum(s["amount"] for s in settlements)
        self.assertGreater(total_settled, 0)


if __name__ == '__main__':
    unittest.main()
