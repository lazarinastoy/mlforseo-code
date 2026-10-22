"""Build example_data/demo.db: a tiny 'products' table, to show generating JSON-LD from a database."""
import sqlite3, pathlib
db = pathlib.Path(__file__).with_name("demo.db")
db.unlink(missing_ok=True)
con = sqlite3.connect(db)
con.execute("""CREATE TABLE products (url TEXT, type TEXT, name TEXT, description TEXT, image TEXT,
               price TEXT, priceCurrency TEXT, availability TEXT, sku TEXT, brand TEXT)""")
con.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?)", [
    ("https://www.example.com/shop/seo-workbook/", "Product", "SEO Audit Workbook", "A printable workbook for technical SEO audits.",
     "https://www.example.com/img/workbook.png", "29.00", "EUR", "InStock", "WB-001", "Example Academy"),
    ("https://www.example.com/shop/schema-cheatsheet/", "Product", "Schema Cheat Sheet", "Every Google-supported type on one page.",
     "https://www.example.com/img/cheatsheet.png", "9.00", "EUR", "PreOrder", "CS-002", "Example Academy"),
])
con.commit(); con.close()
print("wrote", db)
