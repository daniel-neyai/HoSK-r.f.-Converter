def validate_statement(data, config, app):
    opening = data["opening"]
    closing = data["closing"]
    transactions = data["transactions"]

    # Calculate the total amount based on transactions
    total_transaction_amount = sum(tx["amount"] for tx in transactions)

    # Recalculate the closing balance by adding the opening balance and the sum of transactions
    calculated_balance = opening + total_transaction_amount

    # Round balances for comparison
    calculated_balance = round(calculated_balance, 2)
    closing = round(closing, 2)

    # If strict validation is disabled
    if not config.get("strict_validation", True):
        if calculated_balance != closing:
            # Debugging: Print to the console to check if this block is executed
            print(f"Warning: Balance mismatch detected!\nExpected: {closing}\nCalculated: {calculated_balance}")
            
            # Display warning in the GUI
            warning_text = f"Warning: Balance mismatch detected!\nExpected: {closing}\nCalculated: {calculated_balance}\nConversion will continue."
            app.warning_label.config(text=warning_text)  # Update the warning label
            app.append_log(f"Warning: Balance mismatch detected!\nExpected: {closing}\nCalculated: {calculated_balance}")
            return

    # If strict validation is enabled and there's a mismatch, show a warning but continue
    if calculated_balance != closing:
        # Log the warning instead of raising an exception
        app.append_log(f"Warning: Balance mismatch detected!\nExpected: {closing}\nCalculated: {calculated_balance}")
        return

    # If strict validation is enabled and there's a mismatch, show a warning but continue
    if calculated_balance != closing:
        # Log the warning instead of raising an exception
        app.append_log(f"Warning: Balance mismatch detected!\nExpected: {closing}\nCalculated: {calculated_balance}")
        return