"""Generate 3 sample CSV files for the RTM classification app."""

import csv
import random
import os
from datetime import datetime, timedelta

random.seed(42)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 1. Reference data
# ---------------------------------------------------------------------------

MYANMAR_STORE_NAMES = [
    "Aung Min Store", "Golden Star Shop", "Myat Noe Trading", "Shwe Pyi Thar Mart",
    "Thiri Yadanar Store", "Kyaw Zin Mini Mart", "Nay Lin Trading", "Htoo Aung Shop",
    "Mya Thi Da Store", "Win Win Grocery", "Aye Aye Mon Store", "Zaw Zaw Trading",
    "Hla Hla Win Shop", "Kyaw Soe Mart", "Su Su Win Store", "Tun Tun Oo Trading",
    "Min Min Grocery", "Phyo Wai Store", "Saw Myat Shop", "Thu Zar Trading",
    "Khin Maung Store", "Aung Kyaw Mart", "Yin Yin Shop", "Thiha Trading",
    "May Thu Store", "Zay Ya Grocery", "Sein Lwin Store", "Naing Lin Shop",
    "Htet Aung Trading", "Moe Moe Store", "Wai Yan Mart", "Cherry Blossom Shop",
    "San San Aye Store", "Ko Ko Gyi Trading", "Nilar Win Grocery", "Phone Myint Store",
    "Aye Chan Shop", "Soe Min Trading", "Nwe Nwe Store", "Kyaw Kyaw Mart",
    "Thida Oo Shop", "Lin Lin Store", "Aung Zaw Trading", "Mya Mya Grocery",
    "Toe Toe Shop", "Hlaing Myint Store", "Shwe Taung Mart", "Yadanar Trading",
    "City Star Grocery", "Golden Land Shop", "Diamond Store", "Royal Mart",
    "Ocean Blue Grocery", "Green Valley Shop", "Sun Rise Store", "Moon Light Trading",
    "Silver Star Mart", "Happy Shop", "Lucky Star Store", "Best Choice Grocery",
    "Top One Mart", "Mega Store", "Super Save Shop", "Value Plus Trading",
    "Fresh Mart", "Daily Needs Store", "Family Grocery", "Corner Shop Mart",
    "Quick Stop Store", "Home Plus Trading", "Smart Buy Grocery", "Good Price Shop",
    "ABC Mart", "New Day Store", "Fair Deal Trading", "Trust Grocery",
    "Pioneer Shop", "Unity Store", "Modern Mart", "Central Trading",
]

TOWNSHIPS = [
    "Hlaing", "Insein", "Tamwe", "Bahan", "Sanchaung", "Kamayut", "Dagon",
    "Mingalar Taung Nyunt", "Botahtaung", "Pazundaung", "Lanmadaw", "Latha",
    "Kyauktada", "Pabedan", "Ahlone", "Mayangone", "South Okkalapa",
    "North Okkalapa", "Thaketa", "Dawbon", "Yankin", "Thingangyun",
    "Shwe Pyi Thar", "Hlaing Tharyar", "North Dagon", "South Dagon",
    "East Dagon", "Dala", "Seikkyi Kanaungto", "Twantay",
]

STREETS = [
    "Pyay Road", "Kaba Aye Pagoda Road", "University Avenue", "Inya Road",
    "Strand Road", "Bogyoke Aung San Road", "Anawrahta Road", "Mahabandoola Road",
    "Sule Pagoda Road", "Shwedagon Pagoda Road", "Insein Road", "Thanlwin Road",
    "Lower Pazundaung Road", "Upper Pazundaung Road", "Waizayantar Road",
]

CHANNELS = ["General Trade", "Modern Trade", "Wholesales", "Pharmacy"]
CHANNEL_WEIGHTS = [0.55, 0.15, 0.15, 0.15]

BRANDS = [
    "Pantene", "Tide", "Pampers", "Gillette",
    "Oral-B", "Downy", "Safeguard", "Head & Shoulders",
]

ITEM_TYPE_OPTIONS = ["Local", "Import"]
ITEM_CLASS_OPTIONS = ["Nutrition", "Food", "Non Food"]
NUM_IN_BUY_OPTIONS = [12, 24, 48]

# ---------------------------------------------------------------------------
# 2. Build Items (30)
# ---------------------------------------------------------------------------

ITEMS_RAW = [
    ("ITM001", "Pantene Shampoo 170ml",       "Pan Shm 170",  "Pantene",           "Non Food", "170ml"),
    ("ITM002", "Pantene Conditioner 170ml",    "Pan Con 170",  "Pantene",           "Non Food", "170ml"),
    ("ITM003", "Pantene Shampoo 340ml",        "Pan Shm 340",  "Pantene",           "Non Food", "340ml"),
    ("ITM004", "Tide Powder 1kg",              "Tide 1kg",     "Tide",              "Non Food", "1kg"),
    ("ITM005", "Tide Powder 2.5kg",            "Tide 2.5kg",   "Tide",              "Non Food", "2.5kg"),
    ("ITM006", "Tide Liquid 900ml",            "Tide Liq 900", "Tide",              "Non Food", "900ml"),
    ("ITM007", "Pampers Baby Dry S 46pcs",     "Pam S46",      "Pampers",           "Non Food", "S-46pcs"),
    ("ITM008", "Pampers Baby Dry M 40pcs",     "Pam M40",      "Pampers",           "Non Food", "M-40pcs"),
    ("ITM009", "Pampers Baby Dry L 36pcs",     "Pam L36",      "Pampers",           "Non Food", "L-36pcs"),
    ("ITM010", "Pampers Premium Care NB 30pcs","Pam PC NB30",  "Pampers",           "Non Food", "NB-30pcs"),
    ("ITM011", "Gillette Guard Cartridge 4s",  "Gil Guard 4",  "Gillette",          "Non Food", "4pcs"),
    ("ITM012", "Gillette Blue 3 Razor 3s",     "Gil B3 3s",    "Gillette",          "Non Food", "3pcs"),
    ("ITM013", "Gillette Shaving Foam 250ml",  "Gil Foam 250", "Gillette",          "Non Food", "250ml"),
    ("ITM014", "Oral-B Toothbrush Classic",    "OB Classic",   "Oral-B",            "Non Food", "1pc"),
    ("ITM015", "Oral-B Toothpaste 100g",       "OB TP 100",    "Oral-B",            "Non Food", "100g"),
    ("ITM016", "Oral-B Mouthwash 250ml",       "OB MW 250",    "Oral-B",            "Non Food", "250ml"),
    ("ITM017", "Downy Fabric Softener 900ml",  "Dwn 900",      "Downy",             "Non Food", "900ml"),
    ("ITM018", "Downy Fabric Softener 1.8L",   "Dwn 1.8L",     "Downy",             "Non Food", "1.8L"),
    ("ITM019", "Downy Concentrate 370ml",      "Dwn Con 370",  "Downy",             "Non Food", "370ml"),
    ("ITM020", "Safeguard Bar Soap 135g",      "SG Bar 135",   "Safeguard",         "Non Food", "135g"),
    ("ITM021", "Safeguard Liquid Soap 225ml",  "SG Liq 225",   "Safeguard",         "Non Food", "225ml"),
    ("ITM022", "Safeguard Hand Wash 200ml",    "SG HW 200",    "Safeguard",         "Non Food", "200ml"),
    ("ITM023", "H&S Shampoo Cool Menthol 170ml","HS Cool 170", "Head & Shoulders",  "Non Food", "170ml"),
    ("ITM024", "H&S Shampoo Classic Clean 340ml","HS CC 340",  "Head & Shoulders",  "Non Food", "340ml"),
    ("ITM025", "H&S Shampoo Smooth Silky 170ml","HS SS 170",  "Head & Shoulders",  "Non Food", "170ml"),
    ("ITM026", "Enfagrow A+ Stage 3 400g",     "Enfa S3 400",  "Pantene",           "Nutrition","400g"),
    ("ITM027", "Enfagrow A+ Stage 4 900g",     "Enfa S4 900",  "Pantene",           "Nutrition","900g"),
    ("ITM028", "Pringles Original 110g",       "Prgl Orig",    "Tide",              "Food",     "110g"),
    ("ITM029", "Pringles Sour Cream 110g",     "Prgl SC",      "Tide",              "Food",     "110g"),
    ("ITM030", "Vicks VapoRub 50g",            "Vicks 50",     "Safeguard",         "Non Food", "50g"),
]

items = []
for row in ITEMS_RAW:
    items.append({
        "ItemCode": row[0],
        "ItemName": row[1],
        "ShortcutName": row[2],
        "Brand": row[3],
        "Category": row[4],
        "Size": row[5],
    })

item_code_to_brand = {it["ItemCode"]: it["Brand"] for it in items}
item_code_to_class = {it["ItemCode"]: it["Category"] for it in items}

# ---------------------------------------------------------------------------
# 3. Build Customers (80)
# ---------------------------------------------------------------------------

customers = []
for i in range(1, 81):
    code = f"C{i:04d}"
    name = MYANMAR_STORE_NAMES[i - 1]
    township = random.choice(TOWNSHIPS)
    street_no = random.randint(1, 200)
    street = random.choice(STREETS)
    address = f"No.{street_no}, {street}, {township}"
    channel = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS, k=1)[0]
    lat = round(random.uniform(16.80, 17.00), 6)
    lon = round(random.uniform(96.10, 96.20), 6)
    phone = f"09{random.randint(200000000, 999999999)}"
    customers.append({
        "CardCode": code,
        "CardName": name,
        "GroupName": channel,
        "Address": address,
        "Township": township,
        "Channel": channel,
        "Latitude": lat,
        "Longitude": lon,
        "Phone": phone,
    })

# Mark top-10 as heavy buyers (they will get many more transactions)
heavy_buyer_codes = [f"C{i:04d}" for i in range(1, 11)]
# Mark some customers as wholesaler-like (buy lots of Local products)
wholesaler_codes = [f"C{i:04d}" for i in range(1, 6)]

# Force wholesaler-flagged customers into Wholesales or General Trade channel
for c in customers:
    if c["CardCode"] in wholesaler_codes:
        c["Channel"] = random.choice(["Wholesales", "General Trade"])
        c["GroupName"] = c["Channel"]

cus_code_to_name = {c["CardCode"]: c["CardName"] for c in customers}
cus_code_to_channel = {c["CardCode"]: c["Channel"] for c in customers}

# ---------------------------------------------------------------------------
# 4. Build Sales Transactions (~2000 rows)
# ---------------------------------------------------------------------------

START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)
TOTAL_DAYS = (END_DATE - START_DATE).days

item_codes = [f"ITM{i:03d}" for i in range(1, 31)]

sales_rows = []
invoice_counter = 10000

def random_date():
    return START_DATE + timedelta(days=random.randint(0, TOTAL_DAYS))

def make_row(cus_code, item_code, doc_date, invoice_no, pcs_range=(10, 80), amt_range=(5000, 80000)):
    total_pcs = random.randint(*pcs_range)
    total_amount = random.randint(*amt_range)
    item_type = random.choice(ITEM_TYPE_OPTIONS)
    item_class = item_code_to_class.get(item_code, "Non Food")
    brand = item_code_to_brand.get(item_code, random.choice(BRANDS))
    num_in_buy = random.choice(NUM_IN_BUY_OPTIONS)
    return {
        "Cus.Code": cus_code,
        "Cus.Name": cus_code_to_name[cus_code],
        "TotalAmount": total_amount,
        "TotalPcs": total_pcs,
        "DocDate": doc_date.strftime("%d/%m/%Y"),
        "InvoiceNo": f"INV-{invoice_no}",
        "ItemCode": item_code,
        "Outlet Channel": cus_code_to_channel[cus_code],
        "Item Type": item_type,
        "Item Class": item_class,
        "NumInBuy": num_in_buy,
        "BrandName": brand,
    }

# --- Heavy buyers: ~80-120 transactions each for top 10 ---
for cus_code in heavy_buyer_codes:
    n_txn = random.randint(80, 120)
    for _ in range(n_txn):
        invoice_counter += 1
        dt = random_date()
        itm = random.choice(item_codes)
        pcs = (50, 500)
        amt = (50000, 500000)
        row = make_row(cus_code, itm, dt, invoice_counter, pcs_range=pcs, amt_range=amt)
        # Wholesaler-like customers get mostly Local items
        if cus_code in wholesaler_codes:
            row["Item Type"] = "Local"
            row["NumInBuy"] = random.choice([24, 48])
            row["TotalPcs"] = random.randint(100, 500)
        sales_rows.append(row)

# --- Regular customers: ~10-20 transactions each for remaining 70 ---
regular_codes = [f"C{i:04d}" for i in range(11, 81)]
for cus_code in regular_codes:
    n_txn = random.randint(10, 20)
    for _ in range(n_txn):
        invoice_counter += 1
        dt = random_date()
        itm = random.choice(item_codes)
        sales_rows.append(make_row(cus_code, itm, dt, invoice_counter))

random.shuffle(sales_rows)

# ---------------------------------------------------------------------------
# 5. Write CSVs
# ---------------------------------------------------------------------------

# Sales
sales_path = os.path.join(DATA_DIR, "sample_sales.csv")
sales_cols = [
    "Cus.Code", "Cus.Name", "TotalAmount", "TotalPcs", "DocDate",
    "InvoiceNo", "ItemCode", "Outlet Channel", "Item Type", "Item Class",
    "NumInBuy", "BrandName",
]
with open(sales_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=sales_cols)
    w.writeheader()
    w.writerows(sales_rows)

# Customers
cust_path = os.path.join(DATA_DIR, "sample_customers.csv")
cust_cols = [
    "CardCode", "CardName", "GroupName", "Address", "Township",
    "Channel", "Latitude", "Longitude", "Phone",
]
with open(cust_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cust_cols)
    w.writeheader()
    for c in customers:
        w.writerow(c)

# Items
items_path = os.path.join(DATA_DIR, "sample_items.csv")
items_cols = ["ItemCode", "ItemName", "ShortcutName", "Brand", "Category", "Size"]
with open(items_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=items_cols)
    w.writeheader()
    for it in items:
        w.writerow(it)

# ---------------------------------------------------------------------------
# 6. Verify
# ---------------------------------------------------------------------------

import csv as csv2

def count_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        reader = csv2.reader(f)
        header = next(reader)
        rows = sum(1 for _ in reader)
    return rows, len(header)

for label, path in [("sample_sales.csv", sales_path),
                     ("sample_customers.csv", cust_path),
                     ("sample_items.csv", items_path)]:
    nrows, ncols = count_csv(path)
    print(f"{label}: {nrows} rows x {ncols} columns")
