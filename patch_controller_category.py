from pathlib import Path

PATH = Path("force-app/main/default/classes/ProductCatalogController.cls")
OLD = """            SELECT Id, Product2.Name, Product2.Description,
                   UnitPrice, Pricebook2.Name
            FROM PricebookEntry
            WHERE IsActive = true
            AND Pricebook2.Name = :assignedPriceBook
            ORDER BY Product2.Name
            LIMIT 50"""
NEW = """            SELECT Id, Product2.Name, Product2.Description, Product2.Category__c,
                   UnitPrice, Pricebook2.Name
            FROM PricebookEntry
            WHERE IsActive = true
            AND Pricebook2.Name = :assignedPriceBook
            ORDER BY Product2.Category__c, Product2.Name
            LIMIT 200"""

text = PATH.read_text()
if NEW in text:
    print("Already patched.")
elif OLD not in text:
    raise SystemExit("OLD block not found verbatim -- inspect file manually.")
else:
    PATH.write_text(text.replace(OLD, NEW))
    print("Patched ProductCatalogController.cls: added Category__c to SELECT, ordered by category then name, raised LIMIT to 200.")
