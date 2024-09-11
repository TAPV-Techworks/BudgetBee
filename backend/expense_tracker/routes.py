# backend/expense_tracker/routes.py
from __future__ import print_function
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from backend.app_factory import db
from sqlalchemy.exc import SQLAlchemyError
from backend.expense_tracker.views import send_feedback_email, export_to_xlsx
from backend.authentication.models import User
from backend.expense_tracker.models import Expense, Income, Category, Feedback
from backend.authentication.routes import logout_user


expense_tracker_bp = Blueprint('expense_tracker', __name__)


@expense_tracker_bp.route('/income', methods=['POST'])
@login_required
def add_income():
    data = request.get_json()
    amount = data.get('amount')
    category_name = data.get('category')
    date_str = data.get('date')

    date = datetime.strptime(date_str, "%Y-%m-%d").date()  # Ensure date is saved correctly
    month = date.strftime('%B')
    year = date.year

    category = Category.query.filter_by(name=category_name, user_id=current_user.id).first()
    if not category:
        category = Category(name=category_name, user_id=current_user.id)
        db.session.add(category)
        db.session.commit()

    new_income = Income(amount=amount, date=date, month=month, year=year, user_id=current_user.id, category_id=category.id)
    db.session.add(new_income)
    db.session.commit()

    return jsonify({"message": "Income added successfully"}), 201

@expense_tracker_bp.route('/monthly-income', methods=['GET'])
@login_required
def view_income():
    month = request.args.get('month')
    year = request.args.get('year')

    if not month or not year:
        return jsonify({'message': 'Please provide the month and year.'}), 400

    try:
        income_records = Income.query.filter_by(month=month , year=year, user_id=current_user.id).all()
        income_data = [
            {
                "date": income.date.strftime("%Y-%m-%d"),
                "amount": f'{income.amount:,}',
                "category": income.category.name,
                "month": income.month,
                "year": income.year
            } for income in income_records
        ]
    except Exception as e:
        return jsonify({'message': f'Error retrieving income records: {str(e)}'}), 500

    return jsonify(income_data), 200

@expense_tracker_bp.route('/income/<int:income_id>', methods=['PUT'])
@login_required
def update_income(income_id):
    data = request.get_json()
    amount = data.get('amount')
    category_name = data.get('category')
    date_str = data.get('date')

    if not amount or not category_name or not date_str:
        return jsonify({'message': 'Please provide all required fields.'}), 400

    session = db.session()  # Explicitly create a session
    try:
        income = Income.query.filter_by(id=income_id, user_id=current_user.id).first()
        if not income:
            return jsonify({'message': 'Income record not found.'}), 404

        category = Category.query.filter_by(name=category_name, user_id=current_user.id).first()
        if not category:
            category = Category(name=category_name, user_id=current_user.id)
            session.add(category)
            session.commit()

        date = datetime.strptime(date_str, "%Y-%m-%d").date()  # Ensure date is saved correctly
        month = date.strftime('%B')
        year = date.year

        income.amount = amount
        income.category_id = category.id
        income.date = date
        income.month = month
        income.year = year

        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({'message': f'Error updating income: {str(e)}'}), 500
    finally:
        session.close()

    return jsonify({'message': 'Income updated successfully!'}), 200

@expense_tracker_bp.route('/income/<int:income_id>', methods=['DELETE'])
@login_required
def delete_income(income_id):
    session = db.session()  # Explicitly create a session
    try:
        income = Income.query.filter_by(id=income_id, user_id=current_user.id).first()
        if not income:
            return jsonify({'message': 'Income record not found.'}), 404

        session.delete(income)
        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({'message': f'Error deleting income: {str(e)}'}), 500
    finally:
        session.close()

    return jsonify({'message': 'Income deleted successfully!'}), 200

@expense_tracker_bp.route('/expense', methods=['POST'])
@login_required
def add_expense():
    data = request.get_json()
    description = data.get('description')
    amount = data.get('amount')
    category_name = data.get('category')
    date_str = data.get('date')

    if not description or not amount or not category_name or not date_str:
        return jsonify({'message': 'Please provide all required fields.'}), 400

    session = db.session()  # Explicitly create a session
    try:
        category = Category.query.filter_by(name=category_name, user_id=current_user.id).first()
        if not category:
            category = Category(name=category_name, user_id=current_user.id)
            session.add(category)
            session.commit()

        date = datetime.strptime(date_str, '%Y-%m-%d').date()  # Ensure date is saved correctly
        month = date.strftime('%B')
        year = date.year

        new_expense = Expense(description=description, amount=amount, category_id=category.id, date=date, month=month, year=year, user_id=current_user.id)
        session.add(new_expense)
        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({'message': f'Error adding expense: {str(e)}'}), 500
    finally:
        session.close()

    return jsonify({'message': 'Expense added successfully!'}), 201

@expense_tracker_bp.route('/monthly-expenses', methods=['GET'])
@login_required
def get_expenses():
    month = request.args.get('month')
    year = request.args.get('year')

    if not month or not year:
        return jsonify({'message': 'Please provide both month and year.'}), 400

    session = db.session()  # Explicitly create a session
    try:
        expenses = Expense.query.filter_by(month=month, year=year, user_id=current_user.id).all()
        expense_list = [{
            'description': expense.description,
            'amount': f'{expense.amount:,}',
            'category': expense.category.name,
            'date': expense.date.strftime('%Y-%m-%d')
        } for expense in expenses]
    except Exception as e:
        return jsonify({'message': f'Error retrieving expenses: {str(e)}'}), 500
    finally:
        session.close()

    return jsonify(expense_list), 200

@expense_tracker_bp.route('/expense/<int:expense_id>', methods=['PUT'])
@login_required
def update_expense(expense_id):
    data = request.get_json()
    description = data.get('description')
    amount = data.get('amount')
    category_name = data.get('category')
    date_str = data.get('date')

    if not description or not amount or not category_name or not date_str:
        return jsonify({'message': 'Please provide all required fields.'}), 400

    session = db.session()  # Explicitly create a session
    try:
        expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first()
        if not expense:
            return jsonify({'message': 'Expense record not found.'}), 404

        category = Category.query.filter_by(name=category_name, user_id=current_user.id).first()
        if not category:
            category = Category(name=category_name, user_id=current_user.id)
            session.add(category)
            session.commit()

        date = datetime.strptime(date_str, "%Y-%m-%d").date()  # Ensure date is saved correctly
        month = date.strftime('%B')
        year = date.year

        expense.description = description
        expense.amount = amount
        expense.category_id = category.id
        expense.date = date
        expense.month = month
        expense.year = year

        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({'message': f'Error updating expense: {str(e)}'}), 500
    finally:
        session.close()

    return jsonify({'message': 'Expense updated successfully!'}), 200

@expense_tracker_bp.route('/expense/<int:expense_id>', methods=['DELETE'])
@login_required
def delete_expense(expense_id):
    session = db.session()  # Explicitly create a session
    try:
        expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first()
        if not expense:
            return jsonify({'message': 'Expense record not found.'}), 404

        session.delete(expense)
        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({'message': f'Error deleting expense: {str(e)}'}), 500
    finally:
        session.close()

    return jsonify({'message': 'Expense deleted successfully!'}), 200

@expense_tracker_bp.route('/balance', methods=['GET'])
@login_required
def get_balance():
    month = request.args.get('month')
    year = request.args.get('year')

    if not month or not year:
        return jsonify({'message': 'Please provide both month and year.'}), 400

    session = db.session()  # Explicitly create a session
    try:
        income = Income.query.filter_by(month=month, year=year, user_id=current_user.id).all()
        expenses = Expense.query.filter_by(month=month, year=year, user_id=current_user.id).all()

        total_income = sum(income.amount for income in income)
        total_expense = sum(expense.amount for expense in expenses)
        balance = total_income - total_expense if total_income else -total_expense
    except Exception as e:
        return jsonify({'message': f'Error retrieving balance: {str(e)}'}), 500
    finally:
        session.close()

    return jsonify({
        'income': f'{total_income:,}' if total_income else '0',
        'total_expense': f'{total_expense:,}',
        'balance': f'{balance:,}'
    }), 200

@expense_tracker_bp.route('/reset_income', methods=['POST'])
@login_required
def reset_income():
    data = request.get_json()
    month = data.get('month')
    year = data.get('year')

    if not month or not year:
        return jsonify({'message': 'Please provide both month and year.'}), 400

    session = db.session()  # Explicitly create a session
    try:
        income = Income.query.filter_by(month=month, year=year, user_id=current_user.id).first()
        if income:
            income.amount = 0
            session.commit()
        else:
            return jsonify({'message': f'No income record found for {month} {year}.'}), 404
    except Exception as e:
        session.rollback()
        return jsonify({'message': f'Error resetting income: {str(e)}'}), 500
    finally:
        session.close()

    return jsonify({'message': f'Income for {month} {year} reset to zero.'}), 200

@expense_tracker_bp.route('/reset_expenses', methods=['POST'])
@login_required
def reset_expenses():
    data = request.get_json()
    month = data.get('month')
    year = data.get('year')

    if not month or not year:
        return jsonify({'message': 'Please provide both month and year.'}), 400

    session = db.session()  # Explicitly create a session
    try:
        expenses = Expense.query.filter_by(month=month, year=year, user_id=current_user.id).all()
        if expenses:
            for expense in expenses:
                session.delete(expense)
            session.commit()
        else:
            return jsonify({'message': f'No expenses found for {month} {year}.'}), 404
    except Exception as e:
        session.rollback()
        return jsonify({'message': f'Error resetting expenses: {str(e)}'}), 500
    finally:
        session.close()

    return jsonify({'message': f'Expenses for {month} {year} have been deleted.'}), 200

@expense_tracker_bp.route('/feedback', methods=['POST'])
@login_required
def submit_feedback():
    data = request.get_json()
    message = data.get('message')

    if not message:
        return jsonify({'message': 'Feedback message is required.'}), 400

    session = db.session()
    try:
        feedback = Feedback(user_id=current_user.id, message=message)
        session.add(feedback)
        session.commit()

        # Send feedback to admin emails
        send_feedback_email(feedback_message=message)

    except SQLAlchemyError as e:
        session.rollback()
        current_app.logger.error(f"Database error: {str(e)}")
        return jsonify({'message': f'Error submitting feedback: {str(e)}'}), 500
    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'message': f'Error submitting feedback: {str(e)}'}), 500
    finally:
        session.close()

    return jsonify({'message': 'Feedback submitted successfully!'}), 201

@expense_tracker_bp.route('/export-monthly', methods=['GET'])
@login_required
def export_monthly_data():
    month = request.args.get('month')
    year = request.args.get('year')

    if not month or not year:
        return jsonify({'message': 'Please provide both month and year'}), 400

    try:
        year = int(year)
        month_number = datetime.strptime(month, '%B').month

        # Fetch income and expenses based on the provided month and year
        income = Income.query.filter(Income.year == year, 
                                     Income.month == month, 
                                     Income.user_id == current_user.id).all()
                                     
        start_date = datetime(year, month_number, 1)
        end_date = datetime(year, month_number + 1, 1)

        expenses = Expense.query.filter(Expense.date >= start_date, 
                                        Expense.date < end_date, 
                                        Expense.user_id == current_user.id).all()

        if not income and not expenses:
            return jsonify({'message': f'No data available for {month} {year}'}), 404

        filename = f"{current_user.name}_monthly_{month}_{year}.xlsx"
        return export_to_xlsx(income, expenses, filename)
    except ValueError:
        return jsonify({'message': 'Invalid year or month format'}), 400
    except Exception as e:
        return jsonify({'message': f'Error exporting monthly data: {str(e)}'}), 500

@expense_tracker_bp.route('/export-yearly', methods=['GET'])
@login_required
def export_yearly_data():
    year = request.args.get('year', default=datetime.now().year, type=int)

    try:
        # Fetch income and expenses based on the provided year
        income = Income.query.filter(Income.year == year, Income.user_id == current_user.id).all()
        expenses = Expense.query.filter(Expense.date >= datetime(year, 1, 1), 
                                        Expense.date < datetime(year + 1, 1, 1), 
                                        Expense.user_id == current_user.id).all()

        if not income and not expenses:
            return jsonify({'message': f'No data available for {year}'}), 404

        filename = f"{current_user.name}_yearly_{year}.xlsx"
        return export_to_xlsx(income, expenses, filename)
    except Exception as e:
        return jsonify({'message': f'Error exporting yearly data: {str(e)}'}), 500

@expense_tracker_bp.route('/delete_account', methods=['DELETE'])
@login_required
def delete_account():
    session = db.session()  # Explicitly create a session
    try:
        # Delete all expenses associated with the user
        Expense.query.filter_by(user_id=current_user.id).delete()
        
        # Delete all income records associated with the user
        Income.query.filter_by(user_id=current_user.id).delete()

        # Delete all feedback associated with the user
        Feedback.query.filter_by(user_id=current_user.id).delete()
        
        # Delete all categories associated with the user
        Category.query.filter_by(user_id=current_user.id).delete()
        
        # Finally, delete the user account
        User.query.filter_by(id=current_user.id).delete()

        session.commit()

        # Log out the user
        logout_user()

    except Exception as e:
        session.rollback()
        return jsonify({'message': f'Error deleting account: {str(e)}'}), 500
    finally:
        session.close()

    return jsonify({'message': 'Account and all associated data have been deleted successfully.'}), 200
