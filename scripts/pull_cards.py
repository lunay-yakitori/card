"""
python scripts/pull_cards.py
"""

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
        # Try to find headers in thead first
        headers = []
        thead = table.find("thead")
        if thead:
            headers = [th.get_text(strip=True) for th in thead.select("th")]

        # If no thead or headers, try first row of tbody
        if not headers:
            tbody = table.find("tbody")
            if tbody:
                first_row = tbody.find("tr")
                if first_row:
                    headers = [th.get_text(strip=True) for th in first_row.select("th")]

        # If still no headers, try first row of table
        if not headers:
            first_row = table.find("tr")
            if first_row:
                headers = [th.get_text(strip=True) for th in first_row.select("th")]

        if headers and required.issubset(set(headers)):
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

def extract_first_skill(skills_cell):
    """Extract the first skill name from the Max Skill(s) column"""
    # Look for the first <b> tag which contains the skill name
    first_bold = skills_cell.find("b")
    if first_bold:
        return first_bold.get_text(strip=True)
    return ""

def extract_first_skill_display_name(first_skill):
    """Extract the display name of the first skill.

    We don't show the name of the skill. Instead, we just show the level + if it has effect for multiple turns, we should the # of turns.

     α, β, and γ, applying effects for 1 turn, 2 turns, and 3 turns respectively
    
    For example: 
        Preemptive Strike III --> Tier=3
        Bait & Lure γ I  ---> Tier=1 (3 Turns)
        Indirect Approach α II ---> Tier=2 (1 Turn)
    """
    if not first_skill:
        return ""
    
    # Parse the skill name to extract tier and turn effects
    skill_parts = first_skill.split()
    
    # Find the tier (Roman numeral) - usually at the end
    tier = 0
    turns = 0
    
    # Look for Roman numerals (I, II, III, IV, V, etc.)
    for part in skill_parts:
        if part in ['I', 'II', 'III']:
            # Convert Roman numeral to number
            roman_to_num = {'I': 1, 'II': 2, 'III': 3}
            tier = roman_to_num[part]
            break
    
    # Look for Greek letters (α, β, γ) which indicate turn effects
    for part in skill_parts:
        if part in ['α', 'β', 'γ']:
            # Map Greek letters to turn counts
            greek_to_turns = {'α': 1, 'β': 2, 'γ': 3}
            turns = greek_to_turns[part]
            break
    
    # Build the display string    
    if turns > 0:
        return f"Tier={tier} ({turns} Turn{'s' if turns > 1 else ''})"
    else:
        return f"Tier={tier}"

def extract_first_skill_icon(first_skill):
    """Extract the icon of the first skill.
    
    For example:
        Preemptive Strike III --> data/skill_icons/Preemptive_Strike_icon.png
        Bait & Lure γ I  ---> data/skill_icons/Bait_&_Lure_icon.png
        Indirect Approach α II ---> data/skill_icons/Indirect_Approach_icon.png
    """
    if not first_skill:
        return ""
    
    # Clean the skill name by removing Roman numerals, Greek letters, and "Lv. X" parts
    # Keep only the main skill name
    skill_name = first_skill
    
    # Remove Roman numerals (I, II, III)
    skill_name = re.sub(r'\s+I{1,3}\s*', ' ', skill_name)
    
    # Remove Greek letters (α, β, γ)
    skill_name = re.sub(r'\s*[αβγ]\s*', ' ', skill_name)
    
    # Remove "Lv. X" patterns
    skill_name = re.sub(r'\s*Lv\.\s*\d+\s*', ' ', skill_name)
    
    # Clean up extra whitespace and trim
    skill_name = re.sub(r'\s+', ' ', skill_name).strip()
    
    # Map to icon filename
    # Replace spaces and special characters with underscores
    icon_filename = re.sub(r'[^a-zA-Z0-9\s]+', '', skill_name)  # Remove special chars
    icon_filename = re.sub(r'\s+', '_', icon_filename)  # Replace spaces with underscores
    icon_filename = f"{icon_filename}_icon.png"

    return f"data/skill_icons/{icon_filename}"
    
    

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

def update_html_date():
    """Update the date in index.html to reflect when cards were last updated"""
    from datetime import datetime
    
    html_file = "index.html"
    if not os.path.exists(html_file):
        print(f"Warning: {html_file} not found, skipping date update")
        return
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Read the HTML file
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace the date line
    old_pattern = r'<p>Cards database updated on \d{4}-\d{2}-\d{2}</p>'
    new_line = f'<p>Cards database updated on {current_date}</p>'
    
    if re.search(old_pattern, content):
        content, num_replacements = re.subn(old_pattern, new_line, content)
        
        # Write back to the file
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Updated {html_file} with new date: {current_date} (replaced {num_replacements} occurrences)")
    else:
        print(f"Warning: Could not find date pattern in {html_file}")

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
        
        # Extract the first skill
        first_skill = extract_first_skill(tds[idx["Max Skill(s)"]])
        first_skill_icon = extract_first_skill_icon(first_skill)
        first_skill_display_name = extract_first_skill_display_name(first_skill)

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
            "First Skill": first_skill,
            "First Skill Icon": first_skill_icon,
            "First Skill Display Name": first_skill_display_name,
            "Icon URL": icon_url,
            "Local Icon Path": local_path
        })

    df = pd.DataFrame(records)
    print(df.head(5))
    df.to_csv("data/tot_cards_with_icons.csv", index=False)
    
    # Update the HTML file with the current date
    update_html_date()

if __name__ == "__main__":
    main()
