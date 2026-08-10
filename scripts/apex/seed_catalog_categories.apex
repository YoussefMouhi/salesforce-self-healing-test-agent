// Idempotent catalog seeding script.
// Safe to re-run: skips products/pricebook entries that already exist,
// only fills Category__c where it is currently blank.

// ---- Step 1: categorize existing products by name pattern ----
List<Product2> existingToUpdate = new List<Product2>();
for (Product2 p : [SELECT Id, Name, Category__c FROM Product2]) {
    String category = null;
    if (p.Name.startsWith('GenWatt')) {
        category = 'Generators';
    } else if (p.Name.startsWith('Installation:')) {
        category = 'Installation';
    } else if (p.Name.startsWith('SLA:')) {
        category = 'Service Plans';
    } else if (p.Name.startsWith('Test Widget')) {
        category = 'Test Data';
    }
    if (category != null && p.Category__c != category) {
        p.Category__c = category;
        existingToUpdate.add(p);
    }
}
if (!existingToUpdate.isEmpty()) {
    update existingToUpdate;
}
System.debug('Categorized existing products: ' + existingToUpdate.size());

// ---- Step 2: define new products to add ----
List<List<String>> newProducts = new List<List<String>>{
    new List<String>{'GenWatt Diesel 50kW', 'Generators', 'Diesel-powered backup generator, 50kW output.', '18000'},
    new List<String>{'GenWatt Diesel 500kW', 'Generators', 'Diesel-powered backup generator, 500kW output.', '65000'},
    new List<String>{'GenWatt Gasoline 100kW', 'Generators', 'Gasoline-powered backup generator, 100kW output.', '28000'},
    new List<String>{'GenWatt Gasoline 500kW', 'Generators', 'Gasoline-powered backup generator, 500kW output.', '68000'},
    new List<String>{'GenWatt Propane 250kW', 'Generators', 'Propane-powered backup generator, 250kW output.', '42000'},
    new List<String>{'GenWatt Propane 750kW', 'Generators', 'Propane-powered backup generator, 750kW output.', '92000'},
    new List<String>{'GenWatt Natural Gas 200kW', 'Generators', 'Natural gas backup generator, 200kW output.', '38000'},
    new List<String>{'GenWatt Natural Gas 500kW', 'Generators', 'Natural gas backup generator, 500kW output.', '70000'},

    new List<String>{'Installation: Residential', 'Installation', 'Standard residential generator installation.', '3500'},
    new List<String>{'Installation: Commercial - Standard', 'Installation', 'Standard commercial installation package.', '35000'},
    new List<String>{'Installation: Commercial - Premium', 'Installation', 'Premium commercial installation with expedited scheduling.', '60000'},
    new List<String>{'Installation: Remote Site', 'Installation', 'Installation package for remote or hard-to-access sites.', '95000'},
    new List<String>{'Installation: Rush / Same-Day', 'Installation', 'Expedited same-day installation service.', '15000'},

    new List<String>{'SLA: Basic', 'Service Plans', 'Basic annual service level agreement.', '8000'},
    new List<String>{'SLA: 24/7 Emergency Response', 'Service Plans', 'Round-the-clock emergency response coverage.', '55000'},
    new List<String>{'SLA: Preventive Maintenance - Annual', 'Service Plans', 'Annual preventive maintenance visits.', '12000'},
    new List<String>{'SLA: Preventive Maintenance - Quarterly', 'Service Plans', 'Quarterly preventive maintenance visits.', '22000'},

    new List<String>{'Fuel Filter - Standard', 'Parts & Accessories', 'Replacement fuel filter, standard duty.', '85'},
    new List<String>{'Fuel Filter - Heavy Duty', 'Parts & Accessories', 'Replacement fuel filter, heavy duty rated.', '145'},
    new List<String>{'Air Filter - Standard', 'Parts & Accessories', 'Replacement air filter.', '60'},
    new List<String>{'Battery - 12V Starter', 'Parts & Accessories', '12V starter battery for small/medium generators.', '220'},
    new List<String>{'Battery - 24V Starter', 'Parts & Accessories', '24V starter battery for large generators.', '340'},
    new List<String>{'Control Panel - Digital', 'Parts & Accessories', 'Digital control panel upgrade.', '1800'},
    new List<String>{'Remote Monitoring Kit', 'Parts & Accessories', 'Cellular remote monitoring and alerting kit.', '950'},
    new List<String>{'Weatherproof Enclosure', 'Parts & Accessories', 'Weatherproof enclosure for outdoor installations.', '2600'},

    new List<String>{'Diesel Fuel - 55 Gallon Drum', 'Fuel & Consumables', 'Diesel fuel, 55 gallon drum.', '310'},
    new List<String>{'Diesel Fuel - 275 Gallon Tank', 'Fuel & Consumables', 'Diesel fuel, 275 gallon tank.', '1450'},
    new List<String>{'Propane Tank - 100lb', 'Fuel & Consumables', 'Propane tank, 100lb capacity.', '180'},
    new List<String>{'Propane Tank - 420lb', 'Fuel & Consumables', 'Propane tank, 420lb capacity.', '620'},
    new List<String>{'Engine Oil - 15W-40 (5 Gal)', 'Fuel & Consumables', 'Engine oil, 15W-40, 5 gallon pail.', '95'},
    new List<String>{'Coolant - Extended Life (5 Gal)', 'Fuel & Consumables', 'Extended life coolant, 5 gallon pail.', '110'},

    new List<String>{'Operator Training - Half Day', 'Training & Support', 'Half-day on-site operator training.', '1200'},
    new List<String>{'Operator Training - Full Day', 'Training & Support', 'Full-day on-site operator training.', '2200'},
    new List<String>{'Technical Support - Annual Contract', 'Training & Support', 'Annual technical phone/email support contract.', '4500'},
    new List<String>{'Remote Diagnostics Subscription', 'Training & Support', 'Annual subscription to remote diagnostics platform.', '3200'}
};

// ---- Step 3: insert products that don't already exist ----
Set<String> newNames = new Set<String>();
for (List<String> row : newProducts) {
    newNames.add(row[0]);
}
Set<String> existingNames = new Set<String>();
for (Product2 p : [SELECT Name FROM Product2 WHERE Name IN :newNames]) {
    existingNames.add(p.Name);
}

List<Product2> toInsert = new List<Product2>();
Map<String, Decimal> priceByName = new Map<String, Decimal>();
for (List<String> row : newProducts) {
    String name = row[0];
    priceByName.put(name, Decimal.valueOf(row[3]));
    if (!existingNames.contains(name)) {
        Product2 p = new Product2();
        p.Name = name;
        p.Category__c = row[1];
        p.Description = row[2];
        p.IsActive = true;
        toInsert.add(p);
    }
}
if (!toInsert.isEmpty()) {
    insert toInsert;
}
System.debug('Inserted new products: ' + toInsert.size());

// ---- Step 4: create PricebookEntry rows for the NEW products across ALL active pricebooks ----
// Standard entries MUST be inserted before custom-pricebook entries for the same product.
List<Pricebook2> pricebooks = [SELECT Id, Name, IsStandard FROM Pricebook2 WHERE IsActive = true];
System.debug('Active pricebooks found: ' + pricebooks.size());

List<Product2> allNewProducts = [SELECT Id, Name FROM Product2 WHERE Name IN :newNames];
Map<Id, String> productIdToName = new Map<Id, String>();
for (Product2 p : allNewProducts) {
    productIdToName.put(p.Id, p.Name);
}

Set<String> existingEntryKeys = new Set<String>();
for (PricebookEntry pbe : [SELECT Product2Id, Pricebook2Id FROM PricebookEntry WHERE Product2Id IN :productIdToName.keySet()]) {
    existingEntryKeys.add(pbe.Product2Id + '|' + pbe.Pricebook2Id);
}

List<PricebookEntry> standardEntriesToInsert = new List<PricebookEntry>();
List<PricebookEntry> customEntriesToInsert = new List<PricebookEntry>();

for (Id prodId : productIdToName.keySet()) {
    String prodName = productIdToName.get(prodId);
    Decimal price = priceByName.get(prodName);
    for (Pricebook2 pb : pricebooks) {
        String key = prodId + '|' + pb.Id;
        if (existingEntryKeys.contains(key)) {
            continue;
        }
        PricebookEntry pbe = new PricebookEntry();
        pbe.Product2Id = prodId;
        pbe.Pricebook2Id = pb.Id;
        pbe.UnitPrice = price;
        pbe.IsActive = true;
        pbe.UseStandardPrice = false;
        if (pb.IsStandard) {
            standardEntriesToInsert.add(pbe);
        } else {
            customEntriesToInsert.add(pbe);
        }
    }
}

if (!standardEntriesToInsert.isEmpty()) {
    insert standardEntriesToInsert;
}
if (!customEntriesToInsert.isEmpty()) {
    insert customEntriesToInsert;
}
System.debug('Inserted standard PricebookEntries: ' + standardEntriesToInsert.size());
System.debug('Inserted custom PricebookEntries: ' + customEntriesToInsert.size());
System.debug('DONE.');
