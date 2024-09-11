# backend/expense_tracker/views.py
import json
import sib_api_v3_sdk
from backend.app_factory import db
from flask import current_app, send_file
from flask_login import current_user
from sib_api_v3_sdk.rest import ApiException
# from sqlalchemy.exc import IntegrityError
from backend.authentication.models import User
# from backend.expense_tracker.models import Income, Category
from backend.logging_config import setup_logging
from io import BytesIO
from openpyxl import Workbook


logger = setup_logging()

def load_email_config():
    try:
        json_path = 'backend/email_config.json'
        with open(json_path, 'r') as f:
            email_data = json.load(f)
            return email_data
    except FileNotFoundError:
        current_app.logger.error("Email configuration file not found.")
        return None
    except json.JSONDecodeError:
        current_app.logger.error("Error decoding the email configuration file.")
        return None

def send_feedback_email(feedback_message):
    email_config = load_email_config()
    if not email_config:
        return

    try:
        api_key = email_config.get('api_key')

        # Initialize Brevo API client
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key
        api_client = sib_api_v3_sdk.ApiClient(configuration)
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(api_client)

        admin_users = User.query.filter_by(is_admin=True).all()

        sender_email = current_user.email
        sender_name = current_user.name

        for admin in admin_users:
            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                to=[{"email": admin.email, "name": admin.name}],
                sender={"name": sender_name, "email": admin.email},
                subject="New Feedback Received",
                html_content=f"Dear {admin.name},<br>You have received new feedback from {sender_name}:<br><p>{feedback_message}</p><br>All the best,<br>{sender_name}<br>{sender_email}"
            )

            # Send the email
            try:
                api_response = api_instance.send_transac_email(send_smtp_email)
                current_app.logger.info(f"Email sent successfully: {api_response}")
            except ApiException as e:
                current_app.logger.error(f"Exception when calling TransactionalEmailsApi->send_transac_email: {e}")

    except Exception as e:
        current_app.logger.error(f"Failed to send feedback email: {str(e)}")

def export_to_xlsx(income, expenses, filename):
    wb = Workbook()
    ws = wb.active
    ws.title = "Income and Expenses"

    # Headers
    ws.append(["Date", "Type", "Amount", "Category", "Description"])

    # Add income data
    for inc in income:
        ws.append([f"{inc.date}", "Income", inc.amount, inc.category.name if inc.category else ''])

    # Add expenses data
    for exp in expenses:
        ws.append([exp.date.strftime('%Y-%m-%d'), "Expense", exp.amount, exp.category.name if exp.category else '', exp.description])

    # Calculate balance
    total_income = sum(inc.amount for inc in income)
    total_expenses = sum(exp.amount for exp in expenses)
    balance = total_income - total_expenses

    # Add balance
    ws.append([])
    ws.append(["Total Income", total_income])
    ws.append(["Total Expenses", total_expenses])
    ws.append(["Balance", balance])

    # Save to a BytesIO object
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(output, download_name=filename, as_attachment=True)
