from pathlib import Path

PATH = Path("force-app/main/default/lwc/productCatalog/productCatalog.html")
OLD = '''            <div key={entry.Id} class="product-card" data-testid="product-card">
                <span data-testid="product-name">{entry.Product2.Name}</span>'''
NEW = '''            <div key={entry.Id} class="product-card" data-testid="product-card">
                <span data-testid="product-category">{entry.Product2.Category__c}</span>
                <span data-testid="product-name">{entry.Product2.Name}</span>'''

text = PATH.read_text()
if NEW in text:
    print("Already patched.")
elif OLD not in text:
    raise SystemExit("OLD block not found verbatim -- inspect file manually.")
else:
    PATH.write_text(text.replace(OLD, NEW))
    print("Patched productCatalog.html: added product-category span.")
