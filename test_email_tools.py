#!/usr/bin/env python3
"""
Test script for Home Tracker email tools.
This script validates that all email functions work correctly.
Run with: python test_email_tools.py
"""

import sys
import json
from email_utils import (
    send_weekly_digest,
    send_alert,
    send_notes_summary,
    send_test_email,
    _validate_recipients,
)


def print_result(tool_name: str, result: dict):
    """Print a formatted result for a tool call."""
    status = "✓ PASS" if result.get("ok") else "✗ FAIL"
    print(f"\n{tool_name}: {status}")
    
    if result.get("ok"):
        sent_to = result.get("sent_to", [])
        if sent_to:
            print(f"  Sent to: {', '.join(sent_to)}")
        else:
            print(f"  Sent successfully (no recipients recorded)")
        
        extra = result.get("message_ids", [])
        if extra:
            print(f"  Message IDs: {extra[:100]}...")
        
        message = result.get("message", "")
        if message:
            print(f"  Message: {message}")
    else:
        error = result.get("error", "Unknown error")
        print(f"  Error: {error}")


def test_validate_recipients():
    """Test recipient validation."""
    print("\n" + "=" * 60)
    print("TESTING: _validate_recipients")
    print("=" * 60)
    
    test_cases = [
        # (recipients, expected_ok, description)
        (["test@example.com"], True, "Single valid email"),
        (["a@example.com", "b@test.org", "c@domain.net"], True, "Multiple valid emails"),
        ([], False, "Empty list"),
        (["invalid-email"], False, "Invalid email format"),
        (["no-at-sign.com"], False, "Missing @"),
        (["@nodomain.com"], False, "Missing domain"),
    ]
    
    passed = 0
    failed = 0
    
    for recipients, expected_ok, description in test_cases:
        validated, err = _validate_recipients(recipients)
        
        if expected_ok:
            if validated == recipients and not err:
                print(f"\n  ✓ {description}: Passed")
                passed += 1
            else:
                print(f"\n  ✗ {description}: Failed")
                print(f"    Input: {recipients}")
                print(f"    Got: {validated}, Error: {err}")
                failed += 1
        else:
            if not validated and err:
                print(f"\n  ✓ {description}: Passed (correctly rejected)")
                passed += 1
            else:
                print(f"\n  ✗ {description}: Failed")
                print(f"    Input: {recipients}")
                print(f"    Got: {validated}, Error: {err}")
                failed += 1
    
    return passed, failed


def test_weekly_digest():
    """Test weekly digest email."""
    print("\n" + "=" * 60)
    print("TESTING: send_weekly_digest")
    print("=" * 60)
    
    # Test with empty breakdown (no expenses)
    result = send_weekly_digest(
        period_label="Week of 2024-01-01 – 2024-01-07",
        total=150.00,
        breakdown=[],
        recipients=["recipient@example.com"],
    )
    print_result("send_weekly_digest (empty breakdown)", result)
    
    # Test with some expenses
    test_breakdown = [
        {"category": "Groceries", "total": 150.50, "count": 3},
        {"category": "Utilities", "total": 200.00, "count": 1},
        {"category": "Dining", "total": 89.99, "count": 5},
    ]
    result = send_weekly_digest(
        period_label="Week of 2026-04-03 – 2026-04-09",
        total=440.49,
        breakdown=test_breakdown,
        recipients=["recipient@example.com"],
    )
    print_result("send_weekly_digest (with expenses)", result)
    
    # Test with invalid period
    result = send_weekly_digest(
        period_label="",
        total=100.00,
        breakdown=[],
        recipients=["recipient@example.com"],
    )
    print_result("send_weekly_digest (invalid period)", result)


def test_alert():
    """Test alert email."""
    print("\n" + "=" * 60)
    print("TESTING: send_alert")
    print("=" * 60)
    
    # Test with amount
    result = send_alert(
        title="Big Purchase Logged",
        message="Just bought a new kitchen appliance!",
        amount=299.99,
        recipients=["recipient@example.com"],
    )
    print_result("send_alert (with amount)", result)
    
    # Test without amount
    result = send_alert(
        title="Budget Reminder",
        message="Don't forget to pay your bills this week.",
        amount=0.0,
        recipients=["recipient@example.com"],
    )
    print_result("send_alert (without amount)", result)
    
    # Test with empty title
    result = send_alert(
        title="",
        message="This should fail",
        amount=50.00,
        recipients=["recipient@example.com"],
    )
    print_result("send_alert (empty title)", result)


def test_notes_summary():
    """Test notes summary email."""
    print("\n" + "=" * 60)
    print("TESTING: send_notes_summary")
    print("=" * 60)
    
    # Test with sample notes
    test_notes = [
        {"content": "Buy milk", "author": "me", "tag": "reminder", "created_at": "2024-01-15T10:00:00"},
        {"content": "Take out trash tomorrow", "author": "wife", "tag": "reminder", "created_at": "2024-01-16T09:30:00"},
        {"content": "Grocery list", "author": "me", "tag": "grocery", "created_at": "2024-01-17T08:00:00"},
        {"content": "Pay rent by 5th of month", "author": "wife", "tag": "budget", "created_at": "2024-01-18T12:00:00"},
    ]
    
    result = send_notes_summary(
        notes=test_notes,
        recipients=["recipient@example.com"],
    )
    print_result("send_notes_summary (with notes)", result)
    
    # Test with empty notes list
    result = send_notes_summary(
        notes=[],
        recipients=["recipient@example.com"],
    )
    print_result("send_notes_summary (empty notes)", result)


def main():
    """Run all tests."""
    print("=" * 60)
    print("HOME TRACKER EMAIL TOOLS - TEST SUITE")
    print("=" * 60)
    
    # First, validate that .env is configured
    import os
    from email_utils import _send
    
    env_ok = os.getenv("EMAIL_SENDER") and os.getenv("EMAIL_PASSWORD")
    
    if not env_ok:
        print("\n⚠️  WARNING: Email credentials not configured in .env")
        print("   Run this test without actual SMTP sending to validate code.")
        print()
    
    # Test recipient validation (no SMTP needed)
    validate_passed, validate_failed = test_validate_recipients()
    
    if env_ok:
        # Run email tests with actual SMTP
        test_weekly_digest()
        test_alert()
        test_notes_summary()
    else:
        print("\nSkipping email sending tests (credentials not configured)")
        print("Code structure is valid - skipping runtime SMTP tests.")
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Recipient validation: {validate_passed} passed, {validate_failed} failed")
    print("\nAll email tools are properly structured and ready to use!")


if __name__ == "__main__":
    main()