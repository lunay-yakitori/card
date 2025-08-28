import os
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm

URL = "https://tot.wiki/wiki/Cards"
IMG_DIR = "data/icons"
os.makedirs(IMG_DIR, exist_ok=True)

def get_cards_table_soup(url: str) -> BeautifulSoup:
    html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
    soup = BeautifulSoup(html, "lxml")
    
    required = {"Name", "Rarity", "Attribute", "Max Influence", "Max Defense", "Max Skill(s)"}
    
    for table in soup.select("table"):
        print(f"Found table with {len(table.select('tr'))} rows")
        
        # Try to find headers in thead first
        headers = []
        thead = table.find("thead")
        if thead:
            headers = [th.get_text(strip=True) for th in thead.select("th")]
            print(f"Headers from thead: {headers}")
        
        # If no thead or headers, try first row of tbody
        if not headers:
            tbody = table.find("tbody")
            if tbody:
                first_row = tbody.find("tr")
                if first_row:
                    headers = [th.get_text(strip=True) for th in first_row.select("th")]
                    print(f"Headers from first tbody row: {headers}")
        
        # If still no headers, try first row of table
        if not headers:
            first_row = table.find("tr")
            if first_row:
                headers = [th.get_text(strip=True) for th in first_row.select("th")]
                print(f"Headers from first table row: {headers}")
        
        if headers and required.issubset(set(headers)):
            print(f"Found matching table with headers: {headers}")
            return table
    
    # If we get here, let's print all tables to debug
    print("No matching table found. All tables found:")
    for i, table in enumerate(soup.select("table")):
        print(f"\nTable {i}:")
        print(table.prettify()[:500] + "..." if len(table.prettify()) > 500 else table.prettify())
    
    raise RuntimeError("Could not find the cards table")

def extract_text(cell):
    return " ".join(s.strip() for s in cell.stripped_strings)

def parse_name(name_text):
    m = re.search(r'^(.*?)\s+"(.*?)"$', name_text)
    if m:
        return m.group(1), m.group(2)
    parts = re.split(r'"', name_text)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")

def rarity_from_cell(td):
    img = td.find("img")
    if img and img.get("alt"):
        return img["alt"].strip()
    return extract_text(td)

def download_icon(img_url, filename):
    if "width=" not in img_url:
        sep = "&" if "?" in img_url else "?"
        img_url = f"{img_url}{sep}width=50"
    r = requests.get(img_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    if r.ok:
        path = os.path.join(IMG_DIR, filename)
        path = path.replace("_png", ".png")
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(r.content)
        return path
    return None

def main():
    table = get_cards_table_soup(URL)
    print(f"Successfully found table with {len(table.select('tr'))} rows")
    
    # Try to find headers in thead first
    headers = [th.get_text(strip=True) for th in table.select("thead th")]
    
    # If no thead headers, try first row
    if not headers:
        first_row = table.find("tr")
        if first_row:
            headers = [th.get_text(strip=True) for th in first_row.select("th")]
    
    idx = {h: i for i, h in enumerate(headers)}
    print(f"Table headers: {headers}")
    print(f"Column indices: {idx}")
    
    records = []
    # Try tbody first, then fall back to all rows
    rows = table.select("tbody tr")
    if not rows:
        rows = table.select("tr")[1:]  # Skip header row
    
    for tr in tqdm(rows):
        tds = tr.find_all("td")
        if len(tds) < len(idx):
            continue

        name_text = extract_text(tds[idx["Name"]])
        character, card = parse_name(name_text)
        if not card:
            continue

        rarity = rarity_from_cell(tds[idx["Rarity"]])
        attribute = extract_text(tds[idx["Attribute"]])

        # get the icon URL from the img tag in the Name cell
        img = tds[idx["Name"]].find("img")
        icon_url = None
        local_path = None
        if img and img.get("src"):
            icon_url = requests.compat.urljoin(URL, img["src"])
            # make safe filename
            safe_name = re.sub(r'[^a-zA-Z0-9_-]+', "_", f"{character}_{card}.png")
            local_path = download_icon(icon_url, safe_name)

        records.append({
            "Card name": card,
            "Character": character,
            "Rarity": rarity,
            "Attribute": attribute,
            "Icon URL": icon_url,
            "Local Icon Path": local_path
        })

    df = pd.DataFrame(records)
    print(df.head(5))
    df.to_csv("data/tot_cards_with_icons.csv", index=False)

if __name__ == "__main__":
    main()
