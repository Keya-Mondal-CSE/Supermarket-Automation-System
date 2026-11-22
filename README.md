# Supermarket Automation Software (SAS)

A beginner-friendly college project built with **Python Flask, SQLite, HTML, CSS and JavaScript-free server-rendered templates**. The interface uses HTML forms and CSS; Flask handles the backend and SQLite stores the data.

## Main modules

- Customer: register/login, browse/search products, cart, checkout and bill.
- Sales clerk: use the POS screen to enter item code and quantity, handle checkout, and generate bills; view inventory and sales transactions.
- Vendor: receive stock and view supply history.
- Manager: manage products/prices/stock, manage user roles, view sales and reports.
- Inventory: stock is reduced after a completed sale and increased after a recorded supply.

## Requirements

- Python 3.10 or newer
- Visual Studio Code
- VS Code Python extension

## Run in VS Code (Windows)

1. Extract `SAS_Project.zip`.
2. Open VS Code.
3. Select **File → Open Folder** and choose the extracted `SAS_Project` folder (the folder containing `app.py`).
4. Open **Terminal → New Terminal**.
5. Create a virtual environment:

   ```bash
   py -m venv venv
   ```

6. Activate it:

   ```bash
   venv\Scripts\activate
   ```

   If PowerShell blocks activation, run this once in that terminal:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```
   Then activate again.

7. Install packages:

   ```bash
   python -m pip install -r requirements.txt
   ```

8. Start the application:

   ```bash
   python app.py
   ```

9. Open the address printed in the terminal, normally `http://127.0.0.1:5000`.
10. Keep the terminal running while using the application. Press `Ctrl + C` to stop it.

## Run in VS Code (macOS / Linux)

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Then visit `http://127.0.0.1:5000`.

## Demo login accounts

All demo passwords are `1234`.

| Role | Email |
|---|---|
| Customer | customer@sas.com |
| Sales clerk | clerk@sas.com |
| Vendor | vendor@sas.com |
| Manager | manager@sas.com |

You can also register a new customer account from the login page. The manager account can change a user's role from the **Users** page.

## Important testing sequence

1. Login as `manager@sas.com` and open **Inventory**.
2. Add a product or check the sample products.
3. Log out and log in as `vendor@sas.com`.
4. Open **Supply Stock**, choose a product and receive a quantity.
5. Log out and log in as `customer@sas.com`.
6. Browse products, add products to cart, update quantities and checkout.
7. Print the generated bill.
8. Log in as manager and open **Sales** and **Reports** to see the transaction and stock changes.

## Database

The first run automatically creates `sas.db` and inserts sample users/products. The database is stored in this project folder. To reset all demo data, stop the server and delete `sas.db`; it will be recreated on the next run.

## Notes / limitations

- UPI and Card options are **demo-only**. No real money is collected and no payment gateway is connected.
- This is a college-project starter implementation, not a production supermarket system.
- Before public deployment, change `app.secret_key`, disable Flask debug mode, add CSRF protection, validate all workflows, and use a production WSGI server.
- A vendor can record stock received. A real purchase-order approval workflow is not implemented.
- Sales clerk checkout can be extended with a dedicated point-of-sale screen and walk-in customer selection.
