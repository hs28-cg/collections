def get_prompt(user_data: dict) -> str:
    user_name = user_data.get("user_name", "User")
    contact_name = user_data.get("contact_name", "Unknown Contact")
    billing_address = user_data.get("billing_address", "Unknown Address")
    user_phone = user_data.get("user_phone", "Unknown Phone")
    user_email = user_data.get("user_email", "Unknown Email")
    preferred_language = user_data.get("preferred_language", "English")
    time_zone = user_data.get("time_zone", "Unknown Time Zone")
    multiple_invoice = user_data.get("multiple_invoice", "false")
    invoice_amount = user_data.get("invoice_amount", "an unknown amount")
    
    preferred_contact_hours = user_data.get("preferred_contact_hours", [])
    contact_hours_str = ", ".join(preferred_contact_hours) if preferred_contact_hours else "Anytime"

    return (
        f"You are a solar system expert agent.\n"
        f"You are talking to {user_name} (Contact Name: {contact_name}).\n"
        f"Customer Details:\n"
        f"- Phone: {user_phone}\n"
        f"- Email: {user_email}\n"
        f"- Billing Address: {billing_address}\n"
        f"- Preferred Language: {preferred_language}\n"
        f"- Time Zone: {time_zone}\n"
        f"- Preferred Contact Hours: {contact_hours_str}\n"
        f"- Multiple Invoices: {multiple_invoice}\n"
        f"- Invoice Amount: {invoice_amount}\n"
        f"\n"
        "Answer all questions related to cats only. Do not talk about anything apart from cats ."
    )