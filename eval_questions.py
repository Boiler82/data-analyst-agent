"""
Test questions for the Data Analyst Agent.

Each question has:
  - question:   what we ask the agent, in plain English
  - truth_sql:  YOUR SQL query that calculates the correct answer (the "answer key")
  - type:       "number" or "text"
  - tolerance:  (numbers) how far off the agent may be and still count as correct
  - accept:     (text) the answers that count as correct
  - level:      easy / medium / hard / tricky - so you can see where the agent struggles

The correct answers are calculated live from ecommerce.db, so they are always
right for your data. To add a question, copy one block and change it.
"""

QUESTIONS = [
    # ---------- EASY: one table, one calculation ----------
    {
        "question": "How many orders are in the dataset?",
        "truth_sql": "SELECT COUNT(*) FROM orders",
        "type": "number", "tolerance": 0, "level": "easy",
    },
    {
        "question": "How many sellers are there?",
        "truth_sql": "SELECT COUNT(DISTINCT seller_id) FROM sellers",
        "type": "number", "tolerance": 0, "level": "easy",
    },
    {
        "question": "How many orders were canceled?",
        "truth_sql": "SELECT COUNT(*) FROM orders WHERE order_status = 'canceled'",
        "type": "number", "tolerance": 0, "level": "easy",
    },
    {
        "question": "How many orders have the status 'delivered'?",
        "truth_sql": "SELECT COUNT(*) FROM orders WHERE order_status = 'delivered'",
        "type": "number", "tolerance": 0, "level": "easy",
    },
    {
        "question": "What is the average review score across all reviews? Round to 2 decimals.",
        "truth_sql": "SELECT ROUND(AVG(review_score), 2) FROM order_reviews",
        "type": "number", "tolerance": 0.01, "level": "easy",
    },
    {
        "question": "What is the most common payment type?",
        "truth_sql": """SELECT payment_type FROM order_payments
                        GROUP BY payment_type ORDER BY COUNT(*) DESC LIMIT 1""",
        "type": "text", "accept": ["credit_card", "credit card"], "level": "easy",
    },

    # ---------- MEDIUM: totals, dates, grouping ----------
    {
        "question": "What is the total value of all payments, in BRL?",
        "truth_sql": "SELECT SUM(payment_value) FROM order_payments",
        "type": "number", "tolerance": 100, "level": "medium",
    },
    {
        "question": "What is the total freight (shipping) value of all order items, in BRL?",
        "truth_sql": "SELECT SUM(freight_value) FROM order_items",
        "type": "number", "tolerance": 100, "level": "medium",
    },
    {
        "question": "Which customer state has the most customers? Give the state code.",
        "truth_sql": """SELECT customer_state FROM customers
                        GROUP BY customer_state ORDER BY COUNT(*) DESC LIMIT 1""",
        "type": "text", "accept": ["SP", "sao paulo", "são paulo"], "level": "medium",
    },
    {
        "question": "Which month had the most orders? Answer in the format YYYY-MM.",
        "truth_sql": """SELECT strftime('%Y-%m', order_purchase_timestamp) AS month
                        FROM orders GROUP BY month ORDER BY COUNT(*) DESC LIMIT 1""",
        "type": "text", "accept": ["2017-11"], "level": "medium",
    },
    {
        "question": ("For delivered orders, what is the average number of days between "
                     "purchase and delivery to the customer? Round to 1 decimal."),
        "truth_sql": """SELECT ROUND(AVG(julianday(order_delivered_customer_date)
                                         - julianday(order_purchase_timestamp)), 1)
                        FROM orders
                        WHERE order_status = 'delivered'
                          AND order_delivered_customer_date IS NOT NULL""",
        "type": "number", "tolerance": 0.2, "level": "medium",
    },

    # ---------- HARD: joins across several tables ----------
    {
        "question": ("Which product category has the highest total revenue (sum of item prices)? "
                     "Use the English category name."),
        "truth_sql": """SELECT t.product_category_name_english
                        FROM order_items oi
                        JOIN products p ON oi.product_id = p.product_id
                        JOIN product_category_name_translation t
                          ON p.product_category_name = t.product_category_name
                        GROUP BY t.product_category_name_english
                        ORDER BY SUM(oi.price) DESC LIMIT 1""",
        "type": "text", "accept": ["health_beauty", "health beauty", "health and beauty"],
        "level": "hard",
    },
    {
        "question": ("Among delivered orders that have a delivery date, what percentage arrived "
                     "after the estimated delivery date? Round to 1 decimal."),
        "truth_sql": """SELECT ROUND(100.0 * SUM(order_delivered_customer_date > order_estimated_delivery_date)
                                     / COUNT(*), 1)
                        FROM orders
                        WHERE order_status = 'delivered'
                          AND order_delivered_customer_date IS NOT NULL""",
        "type": "number", "tolerance": 0.3, "level": "hard",
    },

    # ---------- TRICKY: a careless analyst would get these wrong ----------
    {
        # Trap: customer_id is different for every order. The real person is customer_unique_id.
        "question": "How many unique customers have placed orders?",
        "truth_sql": "SELECT COUNT(DISTINCT customer_unique_id) FROM customers",
        "type": "number", "tolerance": 0, "level": "tricky",
    },
    {
        # Trap: some orders have no items, so you must count orders from order_items.
        "question": ("On average, how many items does an order contain? Only count orders "
                     "that have at least one item. Round to 2 decimals."),
        "truth_sql": """SELECT ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT order_id), 2)
                        FROM order_items""",
        "type": "number", "tolerance": 0.01, "level": "tricky",
    },
]
