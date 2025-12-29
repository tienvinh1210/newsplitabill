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
    
    def test_partial_cover(self):
        """Test when someone covers part of the bill."""
        people_ids = ["p1", "p2"]
        raw_consumption = {"p1": 60.0, "p2": 40.0}
        total_bill = 100.0
        covers = [{"person_id": "p1", "amount": 20.0}]
        
        final_costs = calculate_final_costs(people_ids, raw_consumption, total_bill, covers)
        
        # Remaining to split: 80
        # p1 pays: (60/100 * 80) + 20 = 48 + 20 = 68
        # p2 pays: (40/100 * 80) + 0 = 32
        self.assertEqual(final_costs["p1"], 68.0)
        self.assertEqual(final_costs["p2"], 32.0)
        self.assertEqual(sum(final_costs.values()), 100.0)
    
    def test_full_cover(self):
        """Test when someone covers the entire bill."""
        people_ids = ["p1", "p2"]
        raw_consumption = {"p1": 60.0, "p2": 40.0}
        total_bill = 100.0
        covers = [{"person_id": "p1", "amount": 100.0}]
        
        final_costs = calculate_final_costs(people_ids, raw_consumption, total_bill, covers)
        
        # Remaining to split: 0
        # p1 pays: 100 (cover only)
        # p2 pays: 0
        self.assertEqual(final_costs["p1"], 100.0)
        self.assertEqual(final_costs["p2"], 0.0)
    
    def test_multiple_covers(self):
        """Test when multiple people cover."""
        people_ids = ["p1", "p2", "p3"]
        raw_consumption = {"p1": 30.0, "p2": 30.0, "p3": 40.0}
        total_bill = 100.0
        covers = [
            {"person_id": "p1", "amount": 10.0},
            {"person_id": "p2", "amount": 20.0}
        ]
        
        final_costs = calculate_final_costs(people_ids, raw_consumption, total_bill, covers)
        
        # Remaining to split: 70
        # p1 pays: (30/100 * 70) + 10 = 21 + 10 = 31
        # p2 pays: (30/100 * 70) + 20 = 21 + 20 = 41
        # p3 pays: (40/100 * 70) + 0 = 28
        self.assertEqual(final_costs["p1"], 31.0)
        self.assertEqual(final_costs["p2"], 41.0)
        self.assertEqual(final_costs["p3"], 28.0)
        self.assertEqual(sum(final_costs.values()), 100.0)


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
